#!/usr/bin/env python3
import ast

with open('ouroboros/agent.py') as f:
    tree = ast.parse(f.read())

funcs = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        arg_count = len([arg for arg in node.args.args if arg.arg != 'self'])
        if arg_count > 8:
            funcs.append(f'{node.name}: {arg_count} params')

print('\n'.join(funcs))