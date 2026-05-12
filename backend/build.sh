#!/bin/bash
echo "🔨 Compiling C HFT engine for Linux..."
gcc -shared -O3 -fPIC -o hft_engine.so hft_engine.c -lm
echo "✅ Compiled successfully!"
ls -la hft_engine.so
