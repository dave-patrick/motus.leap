---
name: ai-assistant
description: "Scaffold an AI assistant with system prompts, tool definitions, conversation management, and safety guardrails."
source: community
allowed-tools: "*"
user-invocable: true
---

# AI Assistant Builder

Scaffold a complete AI assistant with system prompts, tools, conversation management, and safety guardrails.

## STEP 1: DEFINE THE ASSISTANT

Parse $ARGUMENTS for:
- Assistant purpose and domain (customer support, coding, research, etc.)
- Target audience and expected interaction style
- Required capabilities (tools, knowledge, integrations)
- Constraints (cost budget, latency requirements, safety needs)

## STEP 2: DESIGN SYSTEM PROMPT

Create a system prompt that defines:

- **Identity**: Who the assistant is and what it does
- **Capabilities**: What it can and cannot do (be explicit about boundaries)
- **Tone and style**: How it communicates (formal, casual, technical)
- **Instructions**: Specific behavioral rules
- **Output format**: How responses should be structured
- **Safety rules**: What topics to avoid, how to handle edge cases

## STEP 3: DEFINE TOOLS

For each capability that requires external data or actions:

- Tool name and description (clear enough for the LLM to decide when to use it)
- Input schema with types and descriptions
- Output format
- Error handling behavior
- Rate limits or usage constraints

## STEP 4: CONVERSATION MANAGEMENT

Design the conversation flow:

- **Context window management**: How to handle long conversations (summarization, truncation, sliding window)
- **Memory**: What to remember across turns (user preferences, task state)
- **Multi-turn handling**: How to track ongoing tasks across messages
- **Handoff**: When and how to escalate to a human

## STEP 5: SAFETY GUARDRAILS

Implement safety measures:

- Input validation and sanitization
- Output filtering for harmful or inappropriate content
- PII detection and handling
- Prompt injection defenses
- Rate limiting and abuse prevention
- Logging and monitoring for safety review

## STEP 6: SCAFFOLD

Generate the complete implementation with all components wired together, including error handling and observability.
