//! Rendering: the agent connection topology, the conversation, and the input box.

use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};

use crate::app::{App, Speaker};
use crate::rpc::Wiring;

const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

pub fn render(frame: &mut Frame, app: &App) {
    let chunks = Layout::vertical([
        Constraint::Length(11), // topology
        Constraint::Min(3),     // conversation
        Constraint::Length(3),  // input
    ])
    .split(frame.area());

    render_topology(frame, app, chunks[0]);
    render_conversation(frame, app, chunks[1]);
    render_input(frame, app, chunks[2]);
}

fn render_topology(frame: &mut Frame, app: &App, area: Rect) {
    let cols = Layout::horizontal([
        Constraint::Percentage(30),
        Constraint::Length(5),
        Constraint::Percentage(30),
        Constraint::Length(5),
        Constraint::Min(10),
    ])
    .split(area);

    match &app.wiring {
        Some(wiring) => {
            render_agent_box(frame, wiring, cols[0]);
            render_arrow(frame, cols[1], wiring.action_plane.reachable);
            render_action_plane_box(frame, wiring, cols[2]);
            render_arrow(frame, cols[3], wiring.action_plane.reachable);
            render_tools_box(frame, app, wiring, cols[4]);
        }
        None => {
            let block = Block::default().borders(Borders::ALL).title(" topology ");
            frame.render_widget(
                Paragraph::new("Loading agent wiring…").block(block),
                area,
            );
        }
    }
}

fn render_agent_box(frame: &mut Frame, wiring: &Wiring, area: Rect) {
    let agent = &wiring.agent;
    let lines = vec![
        Line::from(vec![Span::raw(agent.name.clone()).bold()]),
        Line::from(Span::styled(short(&agent.id, 22), Style::default().fg(Color::DarkGray))),
        Line::from(format!("persona {}", agent.persona)),
        Line::from(format!("model {}", short(&agent.model, 18))),
        Line::from(""),
        Line::from(vec![
            Span::raw("status "),
            Span::styled(agent.status.clone(), status_style(&agent.status)),
        ]),
    ];
    frame.render_widget(
        Paragraph::new(lines).block(titled("AGENT")),
        area,
    );
}

fn render_action_plane_box(frame: &mut Frame, wiring: &Wiring, area: Rect) {
    let ap = &wiring.action_plane;
    let (dot, label, style) = if ap.reachable {
        ("●", "reachable", Style::default().fg(Color::Green))
    } else {
        ("●", "unreachable", Style::default().fg(Color::Red))
    };
    let lines = vec![
        Line::from(vec![Span::raw(ap.name.clone()).bold()]),
        Line::from(short(&ap.endpoint, 22)),
        Line::from(""),
        Line::from(vec![
            Span::styled(format!("{dot} "), style),
            Span::styled(label, style),
        ]),
    ];
    frame.render_widget(
        Paragraph::new(lines).block(titled("ACTION PLANE")),
        area,
    );
}

fn render_tools_box(frame: &mut Frame, app: &App, wiring: &Wiring, area: Rect) {
    let lines: Vec<Line> = if !wiring.action_plane.reachable {
        vec![Line::from(Span::styled("(action plane unreachable)", Style::default().fg(Color::Red)))]
    } else if wiring.tools.is_empty() {
        vec![Line::from(Span::styled("(no tools)", Style::default().fg(Color::DarkGray)))]
    } else {
        wiring
            .tools
            .iter()
            .map(|tool| {
                let active = app.active_tools.contains(&tool.name);
                let marker = if active { "▸ " } else { "· " };
                let mut style = Style::default();
                if active {
                    style = style.fg(Color::Yellow).bold();
                }
                Line::from(Span::styled(format!("{marker}{}", tool.name), style))
            })
            .collect()
    };
    frame.render_widget(
        Paragraph::new(lines).block(titled("MCP TOOLS")),
        area,
    );
}

fn render_arrow(frame: &mut Frame, area: Rect, reachable: bool) {
    let pad = area.height.saturating_sub(2) / 2;
    let mut lines: Vec<Line> = vec![Line::from(""); pad as usize];
    let style = if reachable {
        Style::default().fg(Color::Green)
    } else {
        Style::default().fg(Color::DarkGray)
    };
    lines.push(Line::from(Span::styled("──▶", style)));
    frame.render_widget(Paragraph::new(lines).alignment(Alignment::Center), area);
}

fn render_conversation(frame: &mut Frame, app: &App, area: Rect) {
    let mut lines: Vec<Line> = Vec::new();
    for entry in &app.conversation {
        let (tag, style) = match entry.speaker {
            Speaker::You => ("you", Style::default().fg(Color::Cyan).bold()),
            Speaker::Agent => (app.agent_name.as_str(), Style::default().fg(Color::Green).bold()),
            Speaker::System => ("·", Style::default().fg(Color::DarkGray)),
        };
        for (i, text_line) in entry.text.split('\n').enumerate() {
            if i == 0 {
                lines.push(Line::from(vec![
                    Span::styled(format!("{tag}> "), style),
                    Span::raw(text_line.to_string()),
                ]));
            } else {
                lines.push(Line::from(format!("    {text_line}")));
            }
        }
    }

    let visible = area.height.saturating_sub(2) as usize;
    let scroll = lines.len().saturating_sub(visible) as u16;
    frame.render_widget(
        Paragraph::new(lines)
            .block(titled("conversation"))
            .wrap(Wrap { trim: false })
            .scroll((scroll, 0)),
        area,
    );
}

fn render_input(frame: &mut Frame, app: &App, area: Rect) {
    let prompt = if app.busy {
        let frame_char = SPINNER[app.spinner % SPINNER.len()];
        Line::from(vec![
            Span::styled(format!("{frame_char} working "), Style::default().fg(Color::Yellow)),
            Span::styled(app.status.clone(), Style::default().fg(Color::DarkGray)),
        ])
    } else {
        Line::from(vec![
            Span::styled("> ", Style::default().fg(Color::Cyan)),
            Span::raw(app.input.clone()),
        ])
    };
    let title = " message · Enter to send · Esc to quit ";
    frame.render_widget(
        Paragraph::new(prompt).block(Block::default().borders(Borders::ALL).title(title)),
        area,
    );
}

fn titled(title: &str) -> Block<'_> {
    Block::default().borders(Borders::ALL).title(format!(" {title} "))
}

fn status_style(status: &str) -> Style {
    match status {
        "idle" => Style::default().fg(Color::Green),
        "processing" => Style::default().fg(Color::Yellow),
        "error" => Style::default().fg(Color::Red),
        _ => Style::default(),
    }
}

fn short(text: &str, max: usize) -> String {
    if text.chars().count() <= max {
        text.to_string()
    } else {
        let kept: String = text.chars().take(max.saturating_sub(1)).collect();
        format!("{kept}…")
    }
}
