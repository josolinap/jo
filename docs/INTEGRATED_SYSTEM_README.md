# Integrated Ouroboros System

## Overview

This is the complete, integrated Ouroboros system that runs automatically without manual intervention.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    TELEGRAM INTERFACE                            │
│  User messages → Telegram Bot → Message Queue                   │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Git    │ │  Model   │ │  Task    │ │ Instance │           │
│  │   Sync   │ │  Router  │ │  Queue   │ │    ID    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT LAYER (6 Agents)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Main   │ │  Coder   │ │Researcher│ │  Tester  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL LAYER (26 Free Models)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ openrouter│stepfun   │arcee-ai   │  ... 23 more│           │
│  │  /free    │/step-3.5 │/trinity   │           │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Git    │ │  Memory  │ │  Local   │ │Instance  │           │
│  │   Sync   │ │  System  │ │  State   │ │    ID    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Automatic Startup

**Method 1: Systemd Service (Recommended)**
```bash
# Start automatically on boot
systemctl start ouroboros

# Check status
systemctl status ouroboros

# View logs
journalctl -u ouroboros -f
```

**Method 2: Direct Python**
```bash
cd /root/jo-project
python3 start_ouroboros.py
```

**Method 3: Cron Job**
```bash
# Added automatically by service_setup.py
@reboot cd /root/jo-project && python3 start_ouroboros.py
```

### 2. Model Orchestration

**26 Free Models Available:**
- `openrouter/free` (default, auto-routing)
- `stepfun/step-3.5-flash:free` (fast coding)
- `arcee-ai/trinity-large-preview:free` (large context)
- And 23 more free models

**Automatic Fallback:**
1. Try requested model
2. If fails, switch to next healthy model
3. Continue until success or all models tried

**Health Monitoring:**
- Tests models every 60 seconds
- Tracks response times
- Maintains healthy models list

### 3. Git Synchronization

**Automatic Sync:**
- Pulls changes from remote every 60 seconds
- Commits local changes with instance ID
- Resolves conflicts automatically
- Pushes changes to GitHub

**Conflict Resolution:**
- Stashes local changes
- Pulls remote changes
- Applies stashed changes
- Manual merge if needed

### 4. Multi-Machine Support

**Each Machine:**
- Gets unique instance ID
- Registers with coordinator
- Syncs changes automatically
- Tracks changes per machine

**Sync Flow:**
```
Machine A → GitHub ← Machine B
    ↓              ↓
Auto-sync     Auto-sync
    ↓              ↓
Changes applied across all machines
```

## Usage

### Starting the System

**Automatic (Recommended):**
```bash
systemctl start ouroboros
```

**Manual:**
```bash
cd /root/jo-project
python3 start_ouroboros.py
```

### Interacting via Telegram

1. Start the system (automatic or manual)
2. Send messages to your Telegram bot
3. System processes using best available model
4. Automatic fallback if model fails
5. Results returned via Telegram

### Checking Status

```bash
# Check if running
systemctl status ouroboros

# View logs
journalctl -u ouroboros -f

# Check instance ID
python3 instance_id.py

# Check model status
python3 model_orchestrator.py
```

## Configuration

### Environment Variables (`.env`)

```bash
# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-...

# Telegram Bot
TELEGRAM_BOT_TOKEN=8210860261:...

# Git Configuration
GIT_USER=OpenCode Agent
GIT_EMAIL=opencode@example.com

# Model Orchestration
ENABLE_MODEL_ORCHESTRATION=1
MAX_MODEL_FALLBACKS=5
```

### Machine-Specific Config (`~/.jo_data/machine_config.json`)

```json
{
  "instance_id": "eed403ff-...",
  "hostname": "arch-linux-pc",
  "platform": "linux",
  "role": "worker",
  "auto_sync": true
}
```

## Multi-Machine Setup

### On Machine 1 (Windows):

```bash
# Clone repository
git clone https://github.com/josolinap/jo.git
cd jo

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Install service
python3 service_setup.py

# Start system
systemctl start ouroboros
```

### On Machine 2 (Arch Linux):

```bash
# Clone repository
git clone https://github.com/josolinap/jo.git
cd jo

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Install service
python3 service_setup.py

# Start system
systemctl start ouroboros
```

**Result:** Both machines automatically sync and coordinate.

## Model Flow Perspective

### Request Processing

```
1. User sends message via Telegram
2. Message enters task queue
3. Model Router selects best model:
   - Check request type (code/research/general)
   - Query health status of models
   - Select fastest healthy model
   - Fallback chain prepared
4. Agent processes request using selected model
5. Response sent back via Telegram
6. Changes committed to git automatically
```

### Model Selection Logic

```python
def select_model(request_type: str) -> str:
    if request_type == "code":
        candidates = ["stepfun/step-3.5-flash:free", "openrouter/free"]
    elif request_type == "research":
        candidates = ["arcee-ai/trinity-large-preview:free", "openrouter/free"]
    else:
        candidates = ["openrouter/free"]
    
    # Filter to healthy models only
    healthy = [m for m in candidates if health_checker.is_healthy(m)]
    
    # Return fastest
    return sorted(healthy, key=lambda m: health_checker.get_response_time(m))[0]
```

## Troubleshooting

### System Won't Start

```bash
# Check service status
systemctl status ouroboros

# Check logs
journalctl -u ouroboros -n 50

# Try manual start
cd /root/jo-project
python3 start_ouroboros.py
```

### Git Sync Issues

```bash
# Check git status
cd /root/jo-project
git status

# Check instance ID
python3 instance_id.py

# Force sync
python3 git_state_manager.py /root/jo-project
```

### Model Failures

```bash
# Check model health
python3 model_orchestrator.py

# Check OpenRouter API key
echo $OPENROUTER_API_KEY

# Test API connection
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models
```

## Current System Status

### Files Created

| File | Purpose |
|------|---------|
| `instance_id.py` | Unique machine identification |
| `git_state_manager.py` | Git operations with conflict resolution |
| `model_orchestrator.py` | 26 free models with health monitoring |
| `ouroboros_system.py` | Fully integrated system |
| `start_ouroboros.py` | Automatic startup script |
| `service_setup.py` | Systemd service installation |
| `ARCHITECTURE_DESIGN.md` | Complete architecture |
| `MULTI_MACHINE_SOLUTION.md` | Multi-machine implementation |

### Features Implemented

✅ **Automatic Startup**: Systemd service or cron job  
✅ **Multi-Machine Sync**: Auto-sync across Windows + Linux  
✅ **Model Orchestration**: 26 free models with fallback  
✅ **Git Integration**: Automatic conflict resolution  
✅ **Task Queue**: Priority-based task processing  
✅ **Identity Persistence**: Unique ID per machine  

### Running Processes

```bash
# Check running processes
ps aux | grep -E "monitor|colab|ouroboros" | grep -v grep

# Expected output:
# - monitor.py (1 process)
# - colab_launcher.py (6 worker processes)
# - ouroboros_system.py (when using integrated system)
```

## Quick Start

### 1. Install & Start (One Time)

```bash
cd /root/jo-project
python3 service_setup.py
systemctl start ouroboros
```

### 2. Verify It's Running

```bash
systemctl status ouroboros
journalctl -u ouroboros -f
```

### 3. Interact via Telegram

Send any message to your bot - the system will:
- Use best available free model
- Automatically fallback on failures
- Sync changes across machines
- Maintain continuous operation

### 4. Add Another Machine

On new machine:
```bash
git clone https://github.com/josolinap/jo.git
cd jo
cp .env.example .env
# Edit .env with API keys
python3 service_setup.py
systemctl start ouroboros
```

**Result:** Both machines coordinate automatically!

## System Architecture Complete

✅ **Fully Automatic**: Starts on boot, no manual intervention  
✅ **Multi-Machine**: Works across Windows + Linux seamlessly  
✅ **Model Resilience**: 26 free models with automatic fallback  
✅ **Identity Persistence**: Unique ID per machine, tracked globally  
✅ **Git Sync**: Automatic conflict resolution and sync  
✅ **Continuous Operation**: Self-healing and auto-restart  

**The system is now fully integrated and ready for production use!**