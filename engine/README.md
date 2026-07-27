# Native Matching Engine

The engine is a C++17 limit order book used by the Python simulator and API. It
models price-time priority, market and limit orders, fills, midpoint/spread
state, and benchmarkable matching behavior.

## Key Files

- `include/`: public C++ order, trade, and order-book types.
- `src/`: matching engine implementation, CLI entry point, and benchmark.
- `bindings/`: pybind11 bridge used by `simulator/engine_adapter.py`.
- `tests/`: C++ and Python bridge tests.

## Local Commands

```powershell
cmake -S engine -B engine/build
cmake --build engine/build --config Debug
ctest --test-dir engine/build --output-on-failure -C Debug
python scripts/container_smoke.py --require-native
```

If the native module is unavailable, the Python adapter can run in stub mode for
some local checks. Release and container smoke checks require the native engine.
