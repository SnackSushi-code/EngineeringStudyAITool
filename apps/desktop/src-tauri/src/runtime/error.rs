use std::fmt;

#[derive(Debug)]
pub enum RuntimeManagerError {
    AlreadyRunning,
    NotRunning,
    ProcessLaunch(String),
    ProcessIo(String),
    Protocol(String),
    ProcessExited(String),
    InvalidResponse(String),
}

impl fmt::Display for RuntimeManagerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AlreadyRunning => write!(f, "Ann-E runtime is already running."),
            Self::NotRunning => write!(f, "Ann-E runtime is not running."),
            Self::ProcessLaunch(message) => {
                write!(f, "Failed to launch Ann-E runtime: {message}")
            }
            Self::ProcessIo(message) => {
                write!(f, "Ann-E runtime I/O error: {message}")
            }
            Self::Protocol(message) => {
                write!(f, "Ann-E runtime protocol error: {message}")
            }
            Self::ProcessExited(message) => {
                write!(f, "Ann-E runtime process exited unexpectedly: {message}")
            }
            Self::InvalidResponse(message) => {
                write!(f, "Invalid Ann-E runtime response: {message}")
            }
        }
    }
}

impl std::error::Error for RuntimeManagerError {}
