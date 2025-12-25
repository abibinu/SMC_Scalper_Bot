# TODO: Fix Spread Too High Issue

## Completed Tasks
- [x] Analyzed the code and identified the issue: MAX_SPREAD_PIPS set to 1.5, but XAUUSD typically has spreads of 2-3 pips
- [x] Increased MAX_SPREAD_PIPS from 1.5 to 3.0 in config.py
- [x] Modified the print statement in main.py to show current spread when skipping for better debugging

## Summary
The "spread too high, skipping" message was appearing because the bot's maximum allowed spread (1.5 pips) was lower than typical spreads for XAUUSD (gold), which often range from 2-3 pips. By increasing the threshold to 3.0 pips and improving the logging, the bot should now handle normal market conditions better.
