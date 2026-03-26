---
id: spec-discord-claude-channels
title: Discord Channels for Remote Claude Code Control
created: 2026-03-26
source: inline
---

# Discord Channels for Remote Claude Code Control

## Problem Statement

Users want to interact with and control Claude Code sessions from multiple devices (phone, tablet, web) without needing direct SSH/VNC access to the host machine. A Discord bot integration would allow sending commands, checking status, and receiving outputs remotely through familiar chat interfaces.

## Goals

- Build a Discord bot that can receive Claude Code commands from Discord channels
- Allow users to initiate, monitor, and interact with Claude Code sessions remotely
- Support multiple concurrent users with session isolation
- Provide real-time output streaming from Claude Code back to Discord
- Enable basic session management (start, stop, check status) via Discord slash commands

## Non-Goals

- Full terminal/SSH replacement - this is command delegation, not remote access
- Voice channel integration
- Complex multi-server bot administration
- Persistent long-running sessions beyond Discord rate limits

## User Stories

- As a user, I can send a `/claude` command in Discord to start a new Claude Code session
- As a user, I can view the status of my active sessions from my phone
- As a user, I can send natural language instructions to an active session and receive responses
- As a user, I can receive file outputs and results from Claude Code back in Discord
- As a user, my sessions are isolated from other users on the same Discord server

## Technical Constraints

- Python 3.10+
- Discord.py or discord-py-interactions for bot framework
- WebSocket or webhook-based communication between Discord bot and Claude Code host
- Claude Code runs on the host machine, Discord bot acts as a bridge
- Rate limit handling for Discord API

## Acceptance Criteria

- [ ] Discord bot connects and responds to `/claude` slash command
- [ ] Bot can spawn Claude Code subprocess and capture stdout/stderr
- [ ] Discord messages can be sent to Claude Code as user input
- [ ] Claude Code output streams back to Discord in real-time (respecting message limits)
- [ ] Multiple users can have isolated sessions simultaneously
- [ ] Sessions can be listed and terminated via Discord commands
- [ ] Basic authentication/authorization (Discord user ID validation)

## Open Questions

- Should sessions persist when Discord disconnects or timeout after inactivity?
- How to handle large output (file uploads, long responses) within Discord limits?
- One bot per host or support multiple hosts via a registration system?
- Security model - who can access which sessions?
