use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Arc, Mutex};

use serde_json::{json, Value};
use uuid::Uuid;

use super::RuntimeManagerError;

const PROTOCOL_VERSION: &str = "1.0";
const RUNTIME_MODULE: &str = "anne_runtime.runtime_host";

struct RuntimeProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

#[derive(Clone)]
pub struct RuntimeManager {
    process: Arc<Mutex<Option<RuntimeProcess>>>,
}

impl RuntimeManager {
    pub fn new() -> Self {
        Self {
            process: Arc::new(Mutex::new(None)),
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

        *process_guard = Some(RuntimeProcess {
            child,
            stdin,
            stdout: BufReader::new(stdout),
        });

        Ok(())
    }

    pub fn is_running(&self) -> Result<bool, RuntimeManagerError> {
        let mut process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        let Some(process) = process_guard.as_mut() else {
            return Ok(false);
        };

        match process.child.try_wait() {
            Ok(None) => Ok(true),
            Ok(Some(status)) => {
                *process_guard = None;

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

        let mut process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        let process = process_guard
            .as_mut()
            .ok_or(RuntimeManagerError::NotRunning)?;

        match process.child.try_wait() {
            Ok(Some(status)) => {
                *process_guard = None;

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

        process
            .stdin
            .write_all(serialized.as_bytes())
            .map_err(|error| {
                RuntimeManagerError::ProcessIo(format!("Unable to write runtime request: {error}"))
            })?;

        process.stdin.write_all(b"\n").map_err(|error| {
            RuntimeManagerError::ProcessIo(format!(
                "Unable to terminate runtime request line: {error}"
            ))
        })?;

        process.stdin.flush().map_err(|error| {
            RuntimeManagerError::ProcessIo(format!("Unable to flush runtime request: {error}"))
        })?;

        let mut response_line = String::new();

        let bytes_read = process
            .stdout
            .read_line(&mut response_line)
            .map_err(|error| {
                RuntimeManagerError::ProcessIo(format!("Unable to read runtime response: {error}"))
            })?;

        if bytes_read == 0 {
            *process_guard = None;

            return Err(RuntimeManagerError::ProcessExited(
                "Runtime host closed stdout before returning a response.".to_string(),
            ));
        }

        let response: Value = serde_json::from_str(response_line.trim()).map_err(|error| {
            RuntimeManagerError::InvalidResponse(format!("Runtime returned invalid JSON: {error}"))
        })?;

        validate_response(&response, &request_id, &task_id)?;

        Ok(response)
    }

    pub fn stop(&self) -> Result<(), RuntimeManagerError> {
        let mut process_guard = self.process.lock().map_err(|_| {
            RuntimeManagerError::ProcessIo("Runtime process lock was poisoned.".to_string())
        })?;

        let Some(mut process) = process_guard.take() else {
            return Ok(());
        };

        drop(process.stdin);

        match process.child.try_wait() {
            Ok(Some(_)) => Ok(()),
            Ok(None) => {
                process.child.kill().map_err(|error| {
                    RuntimeManagerError::ProcessIo(format!(
                        "Unable to terminate runtime host: {error}"
                    ))
                })?;

                process.child.wait().map_err(|error| {
                    RuntimeManagerError::ProcessIo(format!(
                        "Unable to reap runtime host process: {error}"
                    ))
                })?;

                Ok(())
            }
            Err(error) => Err(RuntimeManagerError::ProcessIo(format!(
                "Unable to inspect runtime process during shutdown: {error}"
            ))),
        }
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
            "Runtime response payload must be a JSON object.".to_string(),
        ));
    }

    Ok(())
}
