#!/usr/bin/env python3
"""Fix plan_executor.py - restore -> in type hints, use → only in messages."""
import re

path = '/home/kopyae/Git/simulaca/simulaca_brain/app/modules/cognition/plan_executor.py'
with open(path) as f:
    content = f.read()

# Replace all → back to -> (fixing type hints)
content = content.replace('\u2192', '->')

# Now only replace -> in the move message string
content = content.replace(
    'Moved {context.current_location.name} -> {destination.name}',
    'Moved {context.current_location.name} \u2192 {destination.name}'
)
# Also fix thirst/hunger/fatigue messages that use arrows
content = content.replace(
    'Thirst {old_thirst} -> {new_thirst}',
    'Thirst {old_thirst} \u2192 {new_thirst}'
)
content = content.replace(
    'Hunger {old_hunger} -> {new_hunger}',
    'Hunger {old_hunger} \u2192 {new_hunger}'
)
content = content.replace(
    'Fatigue {old_fatigue} -> {new_fatigue}',
    'Fatigue {old_fatigue} \u2192 {new_fatigue}'
)

with open(path, 'w') as f:
    f.write(content)
print('Fixed')
