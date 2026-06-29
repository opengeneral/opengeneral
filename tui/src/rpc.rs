//! Synchronous JSON-RPC client for the OpenGeneral daemon.
//!
//! The daemon speaks newline-delimited JSON over TCP, one request per connection:
//! connect, write `{"id","method","params"}\n`, read one `{"id","ok","result"|"error"}`
//! line, close. This mirrors the Python `DaemonClient`. The TUI imports no Python —
//! it is just another client of the same language-agnostic localhost protocol.

use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};

pub const DAEMON_NOT_RUNNING: &str =
    "OpenGeneral daemon is not running. Start it with: opengeneral daemon start";

const CONTROL_READ_TIMEOUT: Duration = Duration::from_secs(15);
// An agent turn runs the model and tools, so it can take many seconds.
const AGENT_TURN_READ_TIMEOUT: Duration = Duration::from_secs(600);

#[derive(Clone)]
pub struct Client {
    host: String,
    port: u16,
}

// These mirror the daemon's JSON; unknown keys are ignored, so only the fields the
// TUI renders are declared.
#[derive(Deserialize, Clone, Default, Debug)]
pub struct AgentInfo {
    pub name: String,
    pub id: String,
    pub persona: String,
    pub model: String,
    pub status: String,
}

#[derive(Deserialize, Clone, Default, Debug)]
pub struct ActionPlaneInfo {
    pub name: String,
    pub endpoint: String,
    pub reachable: bool,
}

#[derive(Deserialize, Clone, Default, Debug)]
pub struct ToolInfo {
    pub name: String,
}

#[derive(Deserialize, Clone, Default, Debug)]
pub struct Wiring {
    pub agent: AgentInfo,
    pub action_plane: ActionPlaneInfo,
    #[serde(default)]
    pub tools: Vec<ToolInfo>,
}

#[derive(Deserialize, Default, Debug)]
pub struct MessageReply {
    #[serde(default)]
    pub messages: Vec<String>,
    #[serde(default)]
    pub tools_used: Vec<String>,
}

impl Client {
    #[cfg(test)]
    pub fn new(host: impl Into<String>, port: u16) -> Self {
        Client { host: host.into(), port }
    }

    pub fn from_env() -> Self {
        let host = std::env::var("OPENGENERAL_DAEMON_HOST").unwrap_or_else(|_| "127.0.0.1".into());
        let port = std::env::var("OPENGENERAL_DAEMON_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(4777);
        Client { host, port }
    }

    fn request(&self, method: &str, params: Value, read_timeout: Duration) -> Result<Value, String> {
        let stream = TcpStream::connect((self.host.as_str(), self.port))
            .map_err(|_| DAEMON_NOT_RUNNING.to_string())?;
        stream.set_read_timeout(Some(read_timeout)).ok();

        let payload = json!({"id": "tui", "method": method, "params": params});
        let mut writer = stream.try_clone().map_err(|e| e.to_string())?;
        writeln!(writer, "{payload}").map_err(|_| DAEMON_NOT_RUNNING.to_string())?;
        writer.flush().ok();

        let mut line = String::new();
        BufReader::new(stream)
            .read_line(&mut line)
            .map_err(|_| "OpenGeneral daemon did not respond in time".to_string())?;
        if line.trim().is_empty() {
            return Err("OpenGeneral daemon closed the connection without a response".to_string());
        }

        let resp: Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
        if resp.get("ok").and_then(Value::as_bool).unwrap_or(false) {
            Ok(resp.get("result").cloned().unwrap_or(Value::Null))
        } else {
            Err(resp
                .get("error")
                .and_then(Value::as_str)
                .unwrap_or("OpenGeneral daemon request failed")
                .to_string())
        }
    }

    /// A cheap reachability probe used before entering the full-screen UI.
    pub fn status(&self) -> Result<Value, String> {
        self.request("daemon.status", json!({}), CONTROL_READ_TIMEOUT)
    }

    pub fn agent_list(&self) -> Result<Vec<AgentInfo>, String> {
        let result = self.request("agent.list", json!({}), CONTROL_READ_TIMEOUT)?;
        serde_json::from_value(result).map_err(|e| e.to_string())
    }

    pub fn agent_wiring(&self, name: &str) -> Result<Wiring, String> {
        let result = self.request("agent.wiring", json!({ "name": name }), CONTROL_READ_TIMEOUT)?;
        serde_json::from_value(result).map_err(|e| e.to_string())
    }

    pub fn agent_message(&self, name: &str, content: &str) -> Result<MessageReply, String> {
        let result = self.request(
            "agent.message",
            json!({ "name": name, "content": content, "source": "tui" }),
            AGENT_TURN_READ_TIMEOUT,
        )?;
        serde_json::from_value(result).map_err(|e| e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;
    use std::thread;

    /// Serve a single request: capture the request line, reply with `response`.
    fn serve_once(response: &'static str) -> (u16, mpsc::Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let (stream, _) = listener.accept().unwrap();
            let mut reader = BufReader::new(stream.try_clone().unwrap());
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            tx.send(line).unwrap();
            let mut writer = stream;
            writeln!(writer, "{response}").unwrap();
        });
        (port, rx)
    }

    fn free_port() -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.local_addr().unwrap().port()
    }

    #[test]
    fn parses_wiring_and_sends_the_right_method() {
        let (port, requests) = serve_once(
            r#"{"id":"tui","ok":true,"result":{"agent":{"name":"coder","id":"coder-1","persona":"coder","model":"m","status":"idle"},"action_plane":{"name":"default","endpoint":"http://x/mcp","reachable":true},"tools":[{"name":"echo"}]}}"#,
        );
        let wiring = Client::new("127.0.0.1", port).agent_wiring("coder").unwrap();

        assert_eq!(wiring.agent.name, "coder");
        assert!(wiring.action_plane.reachable);
        assert_eq!(wiring.tools[0].name, "echo");

        let request = requests.recv().unwrap();
        assert!(request.contains("\"method\":\"agent.wiring\""));
        assert!(request.contains("\"name\":\"coder\""));
    }

    #[test]
    fn parses_message_reply_with_tools_used() {
        let (port, _requests) =
            serve_once(r#"{"id":"tui","ok":true,"result":{"messages":["hi"],"tools_used":["echo"]}}"#);
        let reply = Client::new("127.0.0.1", port).agent_message("coder", "hello").unwrap();

        assert_eq!(reply.messages, vec!["hi".to_string()]);
        assert_eq!(reply.tools_used, vec!["echo".to_string()]);
    }

    #[test]
    fn surfaces_daemon_error_responses() {
        let (port, _requests) = serve_once(r#"{"id":"tui","ok":false,"error":"Agent not found: x"}"#);
        let error = Client::new("127.0.0.1", port).agent_wiring("x").unwrap_err();

        assert_eq!(error, "Agent not found: x");
    }

    #[test]
    fn reports_daemon_not_running_when_nothing_listens() {
        let error = Client::new("127.0.0.1", free_port()).agent_list().unwrap_err();

        assert_eq!(error, DAEMON_NOT_RUNNING);
    }
}
