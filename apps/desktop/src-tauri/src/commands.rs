use serde::Serialize;
use serde_json::{json, Value};
use tauri::State;

use crate::runtime::{RuntimeManager, RuntimeManagerError};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeHealth {
    pub connected: bool,
    pub runtime_version: Option<String>,
    pub message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeSession {
    pub session_id: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeMessage {

    pub response_text: String,
    pub stop_reason: String,
    pub iterations: u64,
    pub provider_id: String,
    pub provider_version: String,
    pub model: String,
}

#[tauri::command]
pub fn runtime_health(runtime: State<'_, RuntimeManager>) -> Result<RuntimeHealth, String> {
    ensure_runtime_started(&runtime).map_err(|error| error.to_string())?;

    let response = runtime
        .send_request("health", json!({}))
        .map_err(|error| error.to_string())?;

    parse_health_response(response).map_err(|error| error.to_string())
}


#[tauri::command]
pub fn runtime_create_session(
    runtime: State<'_, RuntimeManager>,
) -> Result<RuntimeSession, String> {
    ensure_runtime_started(&runtime).map_err(|error| error.to_string())?;

    let response = runtime
        .send_request("create_session", json!({}))
        .map_err(|error| error.to_string())?;

    let payload = response
        .get("payload")
        .ok_or_else(|| "Runtime create-session response is missing payload.".to_string())?;

    let session_id = payload
        .get("session_id")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            "Runtime create-session response is missing a valid session_id.".to_string()
        })?;

    Ok(RuntimeSession {
        session_id: session_id.to_string(),
    })
}

#[tauri::command]
pub fn runtime_clear_session(
    runtime: State<'_, RuntimeManager>,
    session_id: String,
) -> Result<(), String> {
    ensure_runtime_started(&runtime).map_err(|error| error.to_string())?;

    if session_id.trim().is_empty() {
        return Err("Session ID cannot be blank.".to_string());
    }

    runtime
        .send_request(
            "clear_session",
            json!({
                "session_id": session_id,
            }),
        )
        .map_err(|error| error.to_string())?;

    Ok(())
}

#[tauri::command]
pub fn runtime_delete_session(
    runtime: State<'_, RuntimeManager>,
    session_id: String,
) -> Result<(), String> {
    ensure_runtime_started(&runtime).map_err(|error| error.to_string())?;

    if session_id.trim().is_empty() {
        return Err("Session ID cannot be blank.".to_string());
    }

    runtime
        .send_request(
            "delete_session",
            json!({
                "session_id": session_id,
            }),
        )
        .map_err(|error| error.to_string())?;

    Ok(())
}
#[tauri::command]
pub fn runtime_message(
    runtime: State<'_, RuntimeManager>,
    session_id: String,
    user_intent: String,
) -> Result<RuntimeMessage, String> {
    ensure_runtime_started(&runtime).map_err(|error| error.to_string())?;

    if user_intent.trim().is_empty() {
        return Err("Message cannot be blank.".to_string());
    }

    let response = runtime
        .send_request(
            "message",
            json!({
                "user_intent": user_intent,
                "session_id": session_id,
            }),
        )
        .map_err(|error| error.to_string())?;

    parse_message_response(response).map_err(|error| error.to_string())
}

fn ensure_runtime_started(runtime: &RuntimeManager) -> Result<(), RuntimeManagerError> {
    match runtime.is_running() {
        Ok(true) => Ok(()),
        Ok(false) => runtime.start(),
        Err(RuntimeManagerError::ProcessExited(_)) => runtime.start(),
        Err(error) => Err(error),
    }
}

fn parse_health_response(response: Value) -> Result<RuntimeHealth, RuntimeManagerError> {
    let status = response
        .get("status")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime health response is missing a valid status.".to_string(),
            )
        })?;

    let payload = response
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime health response is missing a payload object.".to_string(),
            )
        })?;

    let connected = payload
        .get("connected")
        .and_then(Value::as_bool)
        .unwrap_or(status == "completed");

    let runtime_version = payload
        .get("runtime_version")
        .and_then(Value::as_str)
        .map(str::to_owned);

    let message = payload
        .get("message")
        .and_then(Value::as_str)
        .unwrap_or("Ann-E runtime responded without a health message.")
        .to_string();

    Ok(RuntimeHealth {
        connected,
        runtime_version,
        message,
    })
}

fn parse_message_response(response: Value) -> Result<RuntimeMessage, RuntimeManagerError> {
    let status = response
        .get("status")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing a valid status.".to_string(),
            )
        })?;

    let payload = response
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing a payload object.".to_string(),
            )
        })?;

    if status != "completed" {
        let error_message = payload
            .get("error")
            .and_then(Value::as_object)
            .and_then(|error| error.get("message").and_then(Value::as_str))
            .unwrap_or("Ann-E runtime failed to process the message.");

        return Err(RuntimeManagerError::Protocol(error_message.to_string()));
    }

    let response_text = payload
        .get("response_text")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing response_text.".to_string(),
            )
        })?;

    let stop_reason = payload
        .get("stop_reason")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing stop_reason.".to_string(),
            )
        })?;

    let iterations = payload
        .get("iterations")
        .and_then(Value::as_u64)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing iterations.".to_string(),
            )
        })?;

    let provider_id = payload
        .get("provider_id")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing provider_id.".to_string(),
            )
        })?;

    let provider_version = payload
        .get("provider_version")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing provider_version.".to_string(),
            )
        })?;

    let model = payload
        .get("model")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            RuntimeManagerError::InvalidResponse(
                "Runtime message response is missing model.".to_string(),
            )
        })?;

    Ok(RuntimeMessage {
        response_text: response_text.to_string(),
        stop_reason: stop_reason.to_string(),
        iterations,
        provider_id: provider_id.to_string(),
        provider_version: provider_version.to_string(),
        model: model.to_string(),
    })
}
