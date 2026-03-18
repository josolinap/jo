#!/usr/bin/env python3
"""Test the integrated multi-agent orchestrator."""

import asyncio
import sys
sys.path.insert(0, '.')

from integrated_orchestrator import IntegratedOrchestrator

async def test():
    orch = IntegratedOrchestrator()
    status = orch.get_status()

    print('=== Integrated Orchestrator Status ===')
    model_status = status['model_status']
    print(f'Total models discovered: {model_status["total_models"]}')
    print(f'Active model: {model_status["active_model"]}')
    print(f'Fallback chain: {model_status["fallback_chain"]}')

    print('\nAgent status:')
    for role, info in status['agents'].items():
        print(f'  {role}: model={info["current_model"]}, busy={info["busy"]}')

    print('\nTesting workflow...')
    results = await orch.orchestrate_workflow('Review our system architecture')
    print('Workflow results:')
    for phase, result in results.items():
        status_icon = '✅' if result.get('success') else '❌'
        print(f'  {phase}: {status_icon}')

    print('\nTest completed successfully!')

if __name__ == '__main__':
    asyncio.run(test())
