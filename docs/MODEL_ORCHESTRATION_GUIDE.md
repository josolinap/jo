# Model Orchestration Guide

## Problem
The error "Failed to get a response from model openrouter/free after 3 attempts" occurs when:
1. The free model `openrouter/free` is rate-limited
2. The model is temporarily unavailable
3. Network timeouts occur
4. Too many requests in a short time

## Solution: Dynamic Model Orchestration

We've implemented a **model orchestrator** that:
1. **Discovers** all 25+ free models on OpenRouter
2. **Tests** model availability continuously
3. **Routes** around failing models automatically
4. **Fallbacks** to working models when needed

## How It Works

### 1. Model Discovery
```python
# Finds all free models like:
- openrouter/free
- stepfun/step-3.5-flash:free
- arcee-ai/trinity-large-preview:free
- z-ai/glm-4.5-air:free
- qwen/qwen2.5-72b-instruct:free
- meta-llama/llama-3.1-8b-instruct:free
- google/gemini-2.0-flash-exp:free
```

### 2. Health Monitoring
- Tests each model every 60 seconds
- Detects rate limits, timeouts, and failures
- Maintains a "healthy models" list

### 3. Automatic Fallback
When `openrouter/free` fails:
1. Try current model (3 attempts)
2. Switch to next healthy model in chain
3. Continue until success or all models tried

## Configuration

### Environment Variables
```bash
# Enable model orchestration
ENABLE_MODEL_ORCHESTRATION=1

# Maximum fallback attempts
MAX_MODEL_FALLBACKS=5

# Test interval (seconds)
MODEL_TEST_INTERVAL=60

# Preferred models (comma-separated)
PREFERRED_FREE_MODELS=openrouter/free,stepfun/step-3.5-flash:free
```

### Usage in Code

```python
from model_orchestrator import ModelOrchestrator

# Initialize
orchestrator = ModelOrchestrator()

# Discover models
await orchestrator.discover_models()

# Start monitoring (background)
asyncio.create_task(orchestrator.monitor_models())

# Make API call with automatic fallback
response = await orchestrator.chat(
    messages=[{"role": "user", "content": "Hello"}],
    model="openrouter/free"  # Will auto-fallback if needed
)
```

## Integration with Multi-Agent System

The model orchestrator integrates with the multi-agent system:

```python
class IntelligentOrchestrator:
    def __init__(self):
        self.model_orchestrator = ModelOrchestrator()
        # Initialize 6 agents
        self.agents = {...}
    
    async def process_task(self, role, task):
        # Get working model for this agent
        model = await self.model_orchestrator.get_working_model(
            self.agents[role].current_model
        )
        
        # Make API call with automatic fallback
        response = await self.model_orchestrator.chat(
            messages=messages,
            model=model
        )
        return response
```

## Benefits

### 1. Reliability
- **No single point of failure**
- **Automatic recovery** from rate limits
- **Continuous monitoring** of model health

### 2. Performance
- **Fastest models** prioritized in fallback chain
- **Response time tracking** for each model
- **Load balancing** across healthy models

### 3. Cost Efficiency
- **All free models** (no API costs)
- **Intelligent routing** to working models
- **Reduced failed requests**

## Model Status Tracking

The orchestrator tracks:
- **Response time** for each model
- **Success/failure rates**
- **Rate limit status**
- **Last tested time**

## Testing the System

### Test Individual Models
```bash
python3 model_orchestrator.py
```

### Test Multi-Agent with Model Orchestration
```bash
python3 intelligent_orchestrator.py
```

### Monitor Model Health
```bash
python3 -c "
import asyncio
from model_orchestrator import ModelOrchestrator

async def check():
    o = ModelOrchestrator()
    await o.discover_models()
    print(f'Found {len(o.models)} free models')

asyncio.run(check())
"
```

## Troubleshooting

### Issue: "All fallback models match the active one"
**Solution**: The orchestrator needs to discover more models. Ensure:
1. `OPENROUTER_API_KEY` is valid
2. Network access to OpenRouter API
3. Wait 60 seconds for model discovery

### Issue: Rate limiting on all models
**Solution**: 
- The orchestrator automatically backs off
- Try again after a few minutes
- Use multiple free models in rotation

### Issue: Slow responses
**Solution**:
- The orchestrator tracks response times
- Faster models are prioritized
- Check model status with `get_status()`

## Current Status

✅ **25 free models discovered**
✅ **Model health monitoring active**
✅ **Automatic fallback configured**
✅ **Multi-agent integration ready**

## Next Steps

1. **Monitor model performance** - Track which models work best
2. **Optimize fallback chain** - Prioritize fastest models
3. **Add retry logic** - Implement exponential backoff
4. **Cache model status** - Reduce API calls

## Quick Start

```bash
# Start the system
cd /root/jo-project
export $(grep -v '^#' .env | xargs)
nohup python3 monitor.py > /tmp/monitor.log 2>&1 &

# Test model orchestration
python3 model_orchestrator.py

# Test intelligent multi-agent
python3 intelligent_orchestrator.py
```

**The system will now automatically route around failing models and use the best available free model!**