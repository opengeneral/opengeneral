//! TUI application state.

use std::collections::HashSet;

use crate::rpc::Wiring;

#[derive(Clone, Copy, PartialEq)]
pub enum Speaker {
    You,
    Agent,
    System,
}

pub struct ChatLine {
    pub speaker: Speaker,
    pub text: String,
}

/// A result handed back from a background worker thread to the UI loop.
pub enum Update {
    /// A refreshed topology (initial load or periodic refresh).
    Wiring(Wiring),
    /// An agent turn completed: its replies, the tools it used, and fresh wiring.
    Reply {
        messages: Vec<String>,
        tools_used: Vec<String>,
        wiring: Option<Wiring>,
    },
    /// Something failed (daemon down, RPC error). Shown in the status line.
    Failed(String),
}

pub struct App {
    pub agent_name: String,
    pub wiring: Option<Wiring>,
    pub conversation: Vec<ChatLine>,
    pub input: String,
    pub status: String,
    pub busy: bool,
    /// Tools invoked on the most recent turn — highlighted in the topology.
    pub active_tools: HashSet<String>,
    pub spinner: usize,
    pub should_quit: bool,
}

impl App {
    pub fn new(agent_name: String) -> Self {
        App {
            agent_name,
            wiring: None,
            conversation: Vec::new(),
            input: String::new(),
            status: "Connecting to the daemon…".to_string(),
            busy: false,
            active_tools: HashSet::new(),
            spinner: 0,
            should_quit: false,
        }
    }

    pub fn push(&mut self, speaker: Speaker, text: impl Into<String>) {
        self.conversation.push(ChatLine { speaker, text: text.into() });
    }

    pub fn apply(&mut self, update: Update) {
        match update {
            Update::Wiring(wiring) => {
                self.status = wiring_status(&wiring);
                self.wiring = Some(wiring);
            }
            Update::Reply { messages, tools_used, wiring } => {
                for message in messages {
                    self.push(Speaker::Agent, message);
                }
                self.active_tools = tools_used.into_iter().collect();
                if let Some(wiring) = wiring {
                    self.status = wiring_status(&wiring);
                    self.wiring = Some(wiring);
                }
                self.busy = false;
            }
            Update::Failed(error) => {
                self.push(Speaker::System, format!("error: {error}"));
                self.status = error;
                self.busy = false;
            }
        }
    }
}

fn wiring_status(wiring: &Wiring) -> String {
    let reach = if wiring.action_plane.reachable {
        format!("{} tool(s) available", wiring.tools.len())
    } else {
        "Action Plane unreachable".to_string()
    };
    format!("{} · {}", wiring.agent.status, reach)
}
