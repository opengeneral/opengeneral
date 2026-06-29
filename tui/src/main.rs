//! OpenGeneral TUI: visualizes an agent's Action Plane connections (agent ->
//! action plane -> live MCP tools) and drives the chat. It is a pure JSON-RPC
//! client of the daemon — it starts nothing and imports no Python.

mod app;
mod rpc;
mod ui;

use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::Duration;

use ratatui::crossterm::event::{self, Event, KeyCode, KeyEventKind, KeyModifiers};

use app::{App, Speaker, Update};
use rpc::Client;

const POLL: Duration = Duration::from_millis(100);

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        print_usage();
        return;
    }

    let requested_agent = flag_value(&args, "--agent");
    let client = Client::from_env();

    // Fail fast with a plain message if the daemon is down, rather than opening a
    // broken full-screen UI.
    if let Err(error) = client.status() {
        eprintln!("{error}");
        std::process::exit(1);
    }

    let agent_name = match resolve_agent(&client, requested_agent) {
        Ok(name) => name,
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    };

    let mut app = App::new(agent_name);
    match client.agent_wiring(&app.agent_name) {
        Ok(wiring) => app.apply(Update::Wiring(wiring)),
        Err(error) => app.status = error,
    }
    app.push(
        Speaker::System,
        format!("connected to {} — ask it something, or type /tools", app.agent_name),
    );

    let mut terminal = ratatui::init();
    let result = run(&mut terminal, &mut app, &client);
    ratatui::restore();
    if let Err(error) = result {
        eprintln!("opengeneral-tui error: {error}");
        std::process::exit(1);
    }
}

fn run(
    terminal: &mut ratatui::DefaultTerminal,
    app: &mut App,
    client: &Client,
) -> std::io::Result<()> {
    let (tx, rx): (Sender<Update>, Receiver<Update>) = mpsc::channel();

    while !app.should_quit {
        terminal.draw(|frame| ui::render(frame, app))?;

        while let Ok(update) = rx.try_recv() {
            app.apply(update);
        }

        if event::poll(POLL)? {
            if let Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    handle_key(app, client, &tx, key.code, key.modifiers);
                }
            }
        }

        if app.busy {
            app.spinner = app.spinner.wrapping_add(1);
        }
    }
    Ok(())
}

fn handle_key(
    app: &mut App,
    client: &Client,
    tx: &Sender<Update>,
    code: KeyCode,
    modifiers: KeyModifiers,
) {
    if code == KeyCode::Char('c') && modifiers.contains(KeyModifiers::CONTROL) {
        app.should_quit = true;
        return;
    }
    match code {
        KeyCode::Esc => app.should_quit = true,
        KeyCode::Enter => submit(app, client, tx),
        KeyCode::Backspace if !app.busy => {
            app.input.pop();
        }
        KeyCode::Char(c) if !app.busy => app.input.push(c),
        _ => {}
    }
}

fn submit(app: &mut App, client: &Client, tx: &Sender<Update>) {
    if app.busy {
        return;
    }
    let content = app.input.trim().to_string();
    if content.is_empty() {
        return;
    }
    app.input.clear();
    app.push(Speaker::You, content.clone());
    app.busy = true;
    app.status = "thinking…".to_string();

    let client = client.clone();
    let name = app.agent_name.clone();
    let tx = tx.clone();
    thread::spawn(move || {
        let update = match client.agent_message(&name, &content) {
            Ok(reply) => Update::Reply {
                messages: reply.messages,
                tools_used: reply.tools_used,
                wiring: client.agent_wiring(&name).ok(),
            },
            Err(error) => Update::Failed(error),
        };
        let _ = tx.send(update);
    });
}

fn resolve_agent(client: &Client, requested: Option<String>) -> Result<String, String> {
    if let Some(name) = requested {
        return Ok(name);
    }
    let agents = client.agent_list()?;
    match agents.first() {
        Some(agent) => Ok(agent.name.clone()),
        None => Err("No agents are running. Spawn one first: opengeneral spawn --persona <p> --name <n>".to_string()),
    }
}

fn flag_value(args: &[String], flag: &str) -> Option<String> {
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        if arg == flag {
            return iter.next().cloned();
        }
        if let Some(value) = arg.strip_prefix(&format!("{flag}=")) {
            return Some(value.to_string());
        }
    }
    None
}

fn print_usage() {
    println!(
        "opengeneral-tui — visualize an agent's Action Plane connections and chat with it\n\n\
         USAGE:\n    opengeneral-tui [--agent <name>]\n\n\
         If --agent is omitted, the first running agent is used.\n\
         Connects to the daemon at OPENGENERAL_DAEMON_HOST:OPENGENERAL_DAEMON_PORT \
         (default 127.0.0.1:4777)."
    );
}
