use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::{self, Sender},
    Arc, Mutex,
};
use std::thread;

use serde_json::{json, Value};
use uuid::Uuid;

use super::RuntimeManagerError;

const PROTOCOL_VERSION: &str = "1.0";
const RUNTIME_MODULE: &str = "anne_runtime.runtime_host";

type PendingResponseSender = Sender<Result<Value, String>>;

struct PendingRequest {
    task_id: String,
    sender: PendingResponseSender,
}

struct RuntimeProcess {
    child: Arc<Mutex<Child>>,
    stdin: Arc<Mutex<ChildStdin>>,
    shutdown: Arc<AtomicBool>,
}

#[derive(Clone)]
pub struct RuntimeManager {
    process: Arc<Mutex<Option<RuntimeProcess>>>,
    pending: Arc<Mutex<HashMap<String, PendingRequest>>>,
}

impl RuntimeManager {
    pub fn new() -> Self {
        Self {
            process: Arc::new(Mutex::new(None)),
            pending: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn start(&self) -> Result<(), RuntimeManagerError> {
        let mut process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        if process_guard.is_some() {
            return Err(RuntimeManagerError::AlreadyRunning);
        }

        let repository_root = repository_root()?;
        let runtime_source = repository_root.join("services").join("runtime").join("src");

        if !runtime_source.is_dir() {
            return Err(RuntimeManagerError::ProcessLaunch(format!(
                "Runtime source directory was not found: {}",
                runtime_source.display()
            )));
        }

        let runtime_source_string = runtime_source.to_str().ok_or_else(|| {
            RuntimeManagerError::ProcessLaunch(
                "Runtime source path is not valid UTF-8.".to_string(),
            )
        })?;

        let primary_result = Command::new("python")
            .args(["-m", RUNTIME_MODULE])
            .current_dir(&repository_root)
            .env("PYTHONPATH", runtime_source_string)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn();

        let child = match primary_result {
            Ok(child) => child,
            Err(primary_error) => {
                let fallback_result = Command::new("py")
                    .args(["-3.12", "-m", RUNTIME_MODULE])
                    .current_dir(&repository_root)
                    .env("PYTHONPATH", runtime_source_string)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::inherit())
                    .spawn();

                match fallback_result {
                    Ok(child) => child,
                    Err(fallback_error) => {
                        return Err(RuntimeManagerError::ProcessLaunch(format!(
                            "Unable to launch Python runtime host. \
                             Primary error: {}. \
                             Fallback error: {}.",
                            primary_error, fallback_error
                        )));
                    }
                }
            }
        };

        let mut child = child;

        let stdin = match child.stdin.take() {
            Some(stdin) => stdin,
            None => {
                let _ = child.kill();
                let _ = child.wait();

                return Err(RuntimeManagerError::ProcessIo(
                    "Python runtime stdin was not available.".to_string(),
                ));
            }
        };

        let stdout = match child.stdout.take() {
            Some(stdout) => stdout,
            None => {
                let _ = child.kill();
                let _ = child.wait();

                return Err(RuntimeManagerError::ProcessIo(
                    "Python runtime stdout was not available.".to_string(),
                ));
            }
        };

        let child = Arc::new(Mutex::new(child));
        let stdin = Arc::new(Mutex::new(stdin));
        let shutdown = Arc::new(AtomicBool::new(false));

        let runtime_process = RuntimeProcess {
            child: Arc::clone(&child),
            stdin: Arc::clone(&stdin),
            shutdown: Arc::clone(&shutdown),
        };

        *process_guard = Some(runtime_process);

        drop(process_guard);

        self.start_response_reader(stdout, shutdown);

        Ok(())
    }

    fn start_response_reader(&self, stdout: ChildStdout, shutdown: Arc<AtomicBool>) {
        let pending = Arc::clone(&self.pending);

        thread::Builder::new()
            .name("ann-e-runtime-response-reader".to_string())
            .spawn(move || {
                let reader = BufReader::new(stdout);
                response_reader_loop(reader, shutdown, pending);
            })
            .expect("failed to start Ann-E runtime response reader thread");
    }

    pub fn is_running(&self) -> Result<bool, RuntimeManagerError> {
        let process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        let Some(process) = process_guard.as_ref() else {
            return Ok(false);
        };

        let mut child = process.child.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime child lock was poisoned.".to_string())
        })?;

        match child.try_wait() {
            Ok(None) => Ok(true),
            Ok(Some(status)) => {
                drop(child);
                drop(process_guard);

                self.clear_process_if_exited();

                Err(RuntimeManagerError::ProcessExited(format!(
                    "Runtime host exited with status {status}."
                )))
            }
            Err(error) => Err(RuntimeManagerError::ProcessIo(format!(
                "Unable to inspect runtime process state: {error}"
            ))),
        }
    }

    pub fn send_request(
        &self,
        operation: &str,
        payload: Value,
    ) -> Result<Value, RuntimeManagerError> {
        if operation.trim().is_empty() {
            return Err(RuntimeManagerError::Protocol(
                "Runtime operation must not be blank.".to_string(),
            ));
        }

        if !payload.is_object() {
            return Err(RuntimeManagerError::Protocol(
                "Runtime request payload must be a JSON object.".to_string(),
            ));
        }

        let request_id = Uuid::new_v4().to_string();
        let task_id = Uuid::new_v4().to_string();

        let request = json!({
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": request_id,
            "task_id": task_id,
            "operation": operation,
            "payload": payload,
        });

        let serialized = serde_json::to_string(&request).map_err(|error| {
            RuntimeManagerError::Protocol(format!("Unable to serialize runtime request: {error}"))
        })?;

        let (response_sender, response_receiver) = mpsc::channel();

        {
            let mut pending_guard = self.pending.lock().map_err(|_| {
                RuntimeManagerError::ProcessIo(
                    "Runtime pending-request lock was poisoned.".to_string(),
                )
            })?;

            pending_guard.insert(
                request_id.clone(),
                PendingRequest {
                    task_id: task_id.clone(),
                    sender: response_sender,
                },
            );
        }

        let write_result = self.write_request(&serialized);

        if let Err(error) = write_result {
            self.remove_pending_request(&request_id);
            return Err(error);
        }

        match response_receiver.recv() {
            Ok(Ok(response)) => Ok(response),
            Ok(Err(message)) => {
                self.remove_pending_request(&request_id);

                Err(RuntimeManagerError::ProcessIo(message))
            }
            Err(_) => {
                self.remove_pending_request(&request_id);

                Err(RuntimeManagerError::ProcessExited(
                    "Runtime response channel closed before a response was received.".to_string(),
                ))
            }
        }
    }

    fn write_request(&self, serialized: &str) -> Result<(), RuntimeManagerError> {
        let process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        let process = process_guard
            .as_ref()
            .ok_or(RuntimeManagerError::NotRunning)?;

        {
            let mut child = process.child.lock().map_err(|_| {
                RuntimeManagerError::ProcessIo("Runtime child lock was poisoned.".to_string())
            })?;

            match child.try_wait() {
                Ok(Some(status)) => {
                    drop(child);
                    drop(process_guard);

                    self.clear_process_if_exited();

                    return Err(RuntimeManagerError::ProcessExited(format!(
                        "Runtime host exited with status {status}."
                    )));
                }
                Ok(None) => {}
                Err(error) => {
                    return Err(RuntimeManagerError::ProcessIo(format!(
                        "Unable to inspect runtime process state: {error}"
                    )));
                }
            }
        }

        let mut stdin = process.stdin.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime stdin lock was poisoned.".to_string())
        })?;

        stdin.write_all(serialized.as_bytes()).map_err(|error| {
            RuntimeManagerError::ProcessIo(format!("Unable to write runtime request: {error}"))
        })?;

        stdin.write_all(b"\n").map_err(|error| {
            RuntimeManagerError::ProcessIo(format!(
                "Unable to terminate runtime request line: {error}"
            ))
        })?;

        stdin.flush().map_err(|error| {
            RuntimeManagerError::ProcessIo(format!("Unable to flush runtime request: {error}"))
        })?;

        Ok(())
    }

    pub fn stop(&self) -> Result<(), RuntimeManagerError> {
        let process = {
            let mut process_guard = self.process.lock().map_err(|_| {
                RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
            })?;

            process_guard.take()
        };

        let Some(process) = process else {
            self.fail_all_pending(
                "Runtime host was stopped before the response was received.".to_string(),
            );

            return Ok(());
        };

        process.shutdown.store(true, Ordering::SeqCst);

        self.fail_all_pending(
            "Runtime host was stopped before the response was received.".to_string(),
        );

        {
            let mut stdin = process.stdin.lock().map_err(|_| {
                RuntimeManagerError::ProcessIo("Runtime stdin lock was poisoned.".to_string())
            })?;

            let _ = stdin.flush();
        }

        let mut child = process.child.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime child lock was poisoned.".to_string())
        })?;

        match child.try_wait() {
            Ok(Some(_)) => Ok(()),
            Ok(None) => {
                child.kill().map_err(|error| {
                    RuntimeManagerError::ProcessIo(format!(
                        "Unable to terminate runtime host: {error}"
                    ))
                })?;

                child.wait().map_err(|error| {
                    RuntimeManagerError::ProcessIo(format!("Unable to reap runtime host: {error}"))
                })?;

                Ok(())
            }
            Err(error) => Err(RuntimeManagerError::ProcessIo(format!(
                "Unable to inspect runtime process during shutdown: {error}"
            ))),
        }
    }

    fn clear_process_if_exited(&self) {
        let Ok(mut process_guard) = self.process.lock() else {
            return;
        };

        let should_clear = match process_guard.as_ref() {
            Some(process) => match process.child.lock() {
                Ok(mut child) => match child.try_wait() {
                    Ok(Some(_)) => true,
                    Ok(None) => false,
                    Err(_) => false,
                },
                Err(_) => false,
            },
            None => false,
        };

        if should_clear {
            process_guard.take();
        }
    }

    fn remove_pending_request(&self, request_id: &str) {
        if let Ok(mut pending_guard) = self.pending.lock() {
            pending_guard.remove(request_id);
        }
    }

    fn fail_all_pending(&self, message: String) -> usize {
        let pending = {
            let Ok(mut pending_guard) = self.pending.lock() else {
                return 0;
            };

            pending_guard
                .drain()
                .map(|(_, request)| request)
                .collect::<Vec<_>>()
        };

        let count = pending.len();

        for request in pending {
            let _ = request.sender.send(Err(message.clone()));
        }

        count
    }
}

impl Default for RuntimeManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for RuntimeManager {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

fn response_reader_loop<R: BufRead>(
    mut reader: R,
    shutdown: Arc<AtomicBool>,
    pending: Arc<Mutex<HashMap<String, PendingRequest>>>,
) {
    let mut response_line = String::new();

    loop {
        if shutdown.load(Ordering::SeqCst) {
            break;
        }

        response_line.clear();

        match reader.read_line(&mut response_line) {
            Ok(0) => {
                fail_pending_requests(
                    &pending,
                    "Runtime host closed stdout before returning all responses.".to_string(),
                );

                break;
            }
            Ok(_) => {}
            Err(error) => {
                fail_pending_requests(
                    &pending,
                    format!("Unable to read runtime response: {error}"),
                );

                break;
            }
        }

        let response: Value = match serde_json::from_str(response_line.trim()) {
            Ok(response) => response,
            Err(error) => {
                fail_pending_requests(&pending, format!("Runtime returned invalid JSON: {error}"));

                break;
            }
        };

        let request_id = match response.get("request_id").and_then(Value::as_str) {
            Some(request_id) => request_id.to_string(),
            None => {
                fail_pending_requests(
                    &pending,
                    "Runtime response is missing request_id.".to_string(),
                );

                break;
            }
        };

        let pending_request = {
            let Ok(mut pending_guard) = pending.lock() else {
                break;
            };

            pending_guard.remove(&request_id)
        };

        let Some(pending_request) = pending_request else {
            fail_pending_requests(
                &pending,
                format!("Runtime returned a response for unknown request_id '{request_id}'."),
            );

            break;
        };

        let validation = validate_response(&response, &request_id, &pending_request.task_id);

        match validation {
            Ok(()) => {
                let _ = pending_request.sender.send(Ok(response));
            }
            Err(error) => {
                let message = error.to_string();
                let _ = pending_request.sender.send(Err(message));
            }
        }
    }
}

fn fail_pending_requests(pending: &Arc<Mutex<HashMap<String, PendingRequest>>>, message: String) {
    let pending_requests = {
        let Ok(mut pending_guard) = pending.lock() else {
            return;
        };

        pending_guard
            .drain()
            .map(|(_, request)| request)
            .collect::<Vec<_>>()
    };

    for request in pending_requests {
        let _ = request.sender.send(Err(message.clone()));
    }
}

fn repository_root() -> Result<PathBuf, RuntimeManagerError> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));

    manifest_dir
        .join("..")
        .join("..")
        .join("..")
        .canonicalize()
        .map_err(|error| {
            RuntimeManagerError::ProcessLaunch(format!(
                "Unable to resolve repository root: {error}"
            ))
        })
}

fn validate_response(
    response: &Value,
    expected_request_id: &str,
    expected_task_id: &str,
) -> Result<(), RuntimeManagerError> {
    let object = response.as_object().ok_or_else(|| {
        RuntimeManagerError::InvalidResponse("Runtime response must be a JSON object.".to_string())
    })?;

    let required_fields = [
        "protocol_version",
        "type",
        "request_id",
        "task_id",
        "status",
        "payload",
    ];

    for field in required_fields {
        if !object.contains_key(field) {
            return Err(RuntimeManagerError::InvalidResponse(format!(
                "Runtime response is missing required field '{field}'."
            )));
        }
    }

    if object.len() != required_fields.len() {
        return Err(RuntimeManagerError::InvalidResponse(
            "Runtime response contains unknown fields.".to_string(),
        ));
    }

    if object.get("protocol_version").and_then(Value::as_str) != Some(PROTOCOL_VERSION) {
        return Err(RuntimeManagerError::Protocol(
            "Runtime response protocol version is unsupported.".to_string(),
        ));
    }

    if object.get("type").and_then(Value::as_str) != Some("response") {
        return Err(RuntimeManagerError::InvalidResponse(
            "Runtime response type must be 'response'.".to_string(),
        ));
    }

    if object.get("request_id").and_then(Value::as_str) != Some(expected_request_id) {
        return Err(RuntimeManagerError::InvalidResponse(
            "Runtime response request_id does not match the request.".to_string(),
        ));
    }

    if object.get("task_id").and_then(Value::as_str) != Some(expected_task_id) {
        return Err(RuntimeManagerError::InvalidResponse(
            "Runtime response task_id does not match the request.".to_string(),
        ));
    }

    let status = object
        .get("status")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime response status must be a string.".to_string(),
            )
        })?;

    match status {
        "accepted" | "completed" | "failed" | "cancelled" => {}
        _ => {
            return Err(RuntimeManagerError::InvalidResponse(format!(
                "Runtime response status '{status}' is unsupported."
            )));
        }
    }

    if !object.get("payload").is_some_and(Value::is_object) {
        return Err(RuntimeManagerError::InvalidResponse(
            "Runtime response payload must be an object.".to_string(),
        ));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    fn insert_pending_request(
        pending: &Arc<Mutex<HashMap<String, PendingRequest>>>,
        request_id: &str,
        task_id: &str,
    ) -> mpsc::Receiver<Result<Value, String>> {
        let (sender, receiver) = mpsc::channel();

        pending.lock().unwrap().insert(
            request_id.to_string(),
            PendingRequest {
                task_id: task_id.to_string(),
                sender,
            },
        );

        receiver
    }

    fn make_response(request_id: &str, task_id: &str, status: &str) -> Value {
        json!({
            "protocol_version": PROTOCOL_VERSION,
            "type": "response",
            "request_id": request_id,
            "task_id": task_id,
            "status": status,
            "payload": {}
        })
    }

    #[test]
    fn validates_matching_response() {
        let response = make_response("request-1", "task-1", "completed");

        let result = validate_response(&response, "request-1", "task-1");

        assert!(result.is_ok());
    }

    #[test]
    fn rejects_response_with_wrong_request_id() {
        let response = make_response("wrong-request", "task-1", "completed");

        let result = validate_response(&response, "request-1", "task-1");

        assert!(matches!(
            result,
            Err(RuntimeManagerError::InvalidResponse(message))
                if message.contains("request_id does not match")
        ));
    }

    #[test]
    fn rejects_response_with_wrong_task_id() {
        let response = make_response("request-1", "wrong-task", "completed");

        let result = validate_response(&response, "request-1", "task-1");

        assert!(matches!(
            result,
            Err(RuntimeManagerError::InvalidResponse(message))
                if message.contains("task_id does not match")
        ));
    }

    #[test]
    fn rejects_unknown_response_fields() {
        let mut response = make_response("request-1", "task-1", "completed");

        response
            .as_object_mut()
            .unwrap()
            .insert("unexpected".to_string(), json!(true));

        let result = validate_response(&response, "request-1", "task-1");

        assert!(matches!(
            result,
            Err(RuntimeManagerError::InvalidResponse(message))
                if message.contains("unknown fields")
        ));
    }

    #[test]
    fn rejects_unsupported_status() {
        let response = make_response("request-1", "task-1", "running");

        let result = validate_response(&response, "request-1", "task-1");

        assert!(matches!(
            result,
            Err(RuntimeManagerError::InvalidResponse(message))
                if message.contains("unsupported")
        ));
    }

    #[test]
    fn rejects_non_object_payload() {
        let mut response = make_response("request-1", "task-1", "completed");

        response
            .as_object_mut()
            .unwrap()
            .insert("payload".to_string(), json!("not-an-object"));

        let result = validate_response(&response, "request-1", "task-1");

        assert!(matches!(
            result,
            Err(RuntimeManagerError::InvalidResponse(message))
                if message.contains("payload must be an object")
        ));
    }

    #[test]
    fn routes_out_of_order_responses_to_matching_pending_requests() {
        let manager = RuntimeManager::new();

        let first_receiver = insert_pending_request(&manager.pending, "request-1", "task-1");

        let second_receiver = insert_pending_request(&manager.pending, "request-2", "task-2");

        let shutdown = Arc::new(AtomicBool::new(false));
        let pending = Arc::clone(&manager.pending);

        let responses = concat!(
            "{\"protocol_version\":\"1.0\",\"type\":\"response\",",
            "\"request_id\":\"request-2\",\"task_id\":\"task-2\",",
            "\"status\":\"completed\",\"payload\":{}}\n",
            "{\"protocol_version\":\"1.0\",\"type\":\"response\",",
            "\"request_id\":\"request-1\",\"task_id\":\"task-1\",",
            "\"status\":\"completed\",\"payload\":{}}\n"
        );

        response_reader_loop(
            std::io::Cursor::new(responses.as_bytes()),
            shutdown,
            pending,
        );

        let first_response = first_receiver.recv().unwrap().unwrap();
        let second_response = second_receiver.recv().unwrap().unwrap();

        assert_eq!(
            first_response.get("request_id").and_then(Value::as_str),
            Some("request-1")
        );

        assert_eq!(
            second_response.get("request_id").and_then(Value::as_str),
            Some("request-2")
        );
    }

    #[test]
    fn fails_all_pending_requests_when_runtime_closes_stdout() {
        let manager = RuntimeManager::new();

        let first_receiver = insert_pending_request(&manager.pending, "request-1", "task-1");

        let second_receiver = insert_pending_request(&manager.pending, "request-2", "task-2");

        let shutdown = Arc::new(AtomicBool::new(false));
        let pending = Arc::clone(&manager.pending);

        response_reader_loop(std::io::Cursor::new(Vec::<u8>::new()), shutdown, pending);

        let first_result = first_receiver.recv().unwrap();
        let second_result = second_receiver.recv().unwrap();

        assert!(matches!(
            first_result,
            Err(message) if message.contains("closed stdout")
        ));

        assert!(matches!(
            second_result,
            Err(message) if message.contains("closed stdout")
        ));

        assert!(manager.pending.lock().unwrap().is_empty());
    }

    #[test]
    fn fails_all_pending_requests_on_malformed_json() {
        let manager = RuntimeManager::new();

        let receiver = insert_pending_request(&manager.pending, "request-1", "task-1");

        let shutdown = Arc::new(AtomicBool::new(false));
        let pending = Arc::clone(&manager.pending);

        response_reader_loop(
            std::io::Cursor::new(b"{not-valid-json}\n".to_vec()),
            shutdown,
            pending,
        );

        let result = receiver.recv().unwrap();

        assert!(matches!(
            result,
            Err(message) if message.contains("invalid JSON")
        ));

        assert!(manager.pending.lock().unwrap().is_empty());
    }

    #[test]
    fn rejects_unknown_response_request_id_and_fails_pending_requests() {
        let manager = RuntimeManager::new();

        let receiver = insert_pending_request(&manager.pending, "request-1", "task-1");

        let shutdown = Arc::new(AtomicBool::new(false));
        let pending = Arc::clone(&manager.pending);

        let response = make_response("unknown-request", "task-unknown", "completed");
        let serialized = format!("{response}\n");

        response_reader_loop(
            std::io::Cursor::new(serialized.into_bytes()),
            shutdown,
            pending,
        );

        let result = receiver.recv().unwrap();

        assert!(matches!(
            result,
            Err(message) if message.contains("unknown request_id")
        ));

        assert!(manager.pending.lock().unwrap().is_empty());
    }

    #[test]
    fn stop_releases_pending_requests_without_process() {
        let manager = RuntimeManager::new();

        let receiver = insert_pending_request(&manager.pending, "request-1", "task-1");

        manager.stop().unwrap();

        let result = receiver.recv().unwrap();

        assert!(matches!(
            result,
            Err(message) if message.contains("stopped")
        ));

        assert!(manager.pending.lock().unwrap().is_empty());
    }

    #[test]
    fn stop_is_idempotent_when_runtime_is_already_stopped() {
        let manager = RuntimeManager::new();

        assert!(manager.stop().is_ok());
        assert!(manager.stop().is_ok());
    }

    #[test]
    fn stop_releases_a_real_blocked_send_request() {
        let manager = RuntimeManager::new();

        let mut child = spawn_blocking_test_process();

        let stdin = child
            .stdin
            .take()
            .expect("blocking test process stdin should be available");

        let _stdout = child
            .stdout
            .take()
            .expect("blocking test process stdout should be available");

        let shutdown = Arc::new(AtomicBool::new(false));

        {
            let mut process_guard = manager.process.lock().unwrap();

            process_guard.replace(RuntimeProcess {
                child: Arc::new(Mutex::new(child)),
                stdin: Arc::new(Mutex::new(stdin)),
                shutdown,
            });
        }

        let request_manager = manager.clone();

        let request_thread = thread::spawn(move || {
            request_manager.send_request("test_blocking_operation", json!({}))
        });

        let deadline = Instant::now() + Duration::from_secs(2);

        loop {
            let pending_count = manager.pending.lock().unwrap().len();

            if pending_count == 1 {
                break;
            }

            assert!(
                Instant::now() < deadline,
                "send_request did not register its pending request in time"
            );

            thread::yield_now();
        }

        manager.stop().unwrap();

        let result = request_thread
            .join()
            .expect("blocked send_request thread should terminate after stop");

        match result {
            Err(RuntimeManagerError::ProcessIo(message)) => {
                assert!(
                    message.contains("stopped before the response"),
                    "unexpected shutdown error: {message}"
                );
            }
            other => {
                panic!(
                    "expected ProcessIo shutdown error, got: {other:?}"
                );
            }
        }

        assert!(
            manager.pending.lock().unwrap().is_empty(),
            "stop must release all pending requests"
        );

        assert!(
            !manager.is_running().unwrap(),
            "runtime manager must report no running process after stop"
        );
    }

    fn spawn_blocking_test_process() -> Child {
        let primary_result = Command::new("python")
            .args(["-c", "import time; time.sleep(60)"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn();

        match primary_result {
            Ok(child) => child,
            Err(primary_error) => Command::new("py")
                .args(["-3.12", "-c", "import time; time.sleep(60)"])
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
                .unwrap_or_else(|fallback_error| {
                    panic!(
                        "Unable to launch blocking test process. \
                             Primary error: {primary_error}. \
                             Fallback error: {fallback_error}."
                    )
                }),
        }
    }
}
