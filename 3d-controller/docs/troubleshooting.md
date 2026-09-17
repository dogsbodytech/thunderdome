# Troubleshooting

Start with the first check in the table. Do not skip the simulator gate to debug physical DDP. A physical symptom can be caused by power, wiring, WLED settings, network, mapping, or Python; isolate one layer at a time.

| Symptom | Likely causes | First check | Next step |
| --- | --- | --- | --- |
| `thunderdome` command not found | venv is not active; package not installed | Run `source .venv/bin/activate` and `thunderdome --help` | [Rebuild/install](commissioning/rebuild-controller-host.md) |
| Venv problems | Python older than 3.11; venv package missing; broken environment | Run `python3 --version` and `test -x .venv/bin/python` | Recreate `.venv` and follow [software setup](runbooks/software-and-simulator.md) |
| Missing generated positions | Fresh checkout; ignored derived file absent | Run `test -f geometry/generated/led_positions_3d.json` | Run `thunderdome positions generate`, then validate |
| Geometry validation failure | Wrong file; edited geometry; incompatible path | Run `thunderdome geometry validate` and note the resolved path | Restore/obtain the authoritative geometry; see [source of truth](reference/source-of-truth.md#geometry) |
| Route validation failure | Route file does not match geometry; invalid spar/hub; manual route edit | Run `thunderdome route validate` | Use `geometry/routes/string_routes.json`; do not infer a route by symmetry |
| Position validation failure | Generated file is stale or from different geometry/routes | Run `thunderdome positions generate` followed by `thunderdome positions validate` | Keep geometry, routes, and positions from the same checkout |
| Simulator will not start | Port occupied; missing/invalid positions; incompatible data | Run `thunderdome simulator serve --host 127.0.0.1 --port 8080 --no-open-browser` and read the error | Generate positions or choose a free local port; do not debug WLED |
| Browser cannot open simulator | Server stopped; wrong URL/port; browser local access issue | Confirm the server printed `http://127.0.0.1:8080/` and is still running | Open the printed URL or use `--port`; see [simulator reference](simulator.md) |
| Simulator loads but no live movement | Effect not started; wrong simulator URL; producer connection failed | Run a finite effect with `--output simulator` and check the CLI output mode | Check `/ws/producer` and [software runbook](runbooks/software-and-simulator.md) |
| Simulator works but physical dome is dark | No power; WLED off; wrong host; realtime/DDP disabled; wiring/fuse issue | Read WLED state and check controller reachability | Follow [physical startup](runbooks/physical-dome-startup.md) and [first light](runbooks/first-light-and-ddp.md) |
| Controller config invalid | Placeholder host; wrong number/string/range; malformed JSON | Run `thunderdome controllers validate --controllers config/controllers.json` | Recreate from `config/controllers.example.json`; see [WLED commissioning](commissioning/wled-controller.md#controllersjson) |
| One WLED controller unreachable | Network path; wrong address; device off; controller fault | Ping the exact address, then run `thunderdome controller info --host ADDRESS` | Compare with [controller network](reference/controller-network.md); do not substitute an unrecorded address |
| One LED string dark | PSU/injection/fuse/data wiring; wrong controller/string identity; WLED output setting | Test that controller with a finite `ddp solid` frame and read its WLED state | Isolate wiring/power versus mapping; use the physical installation documents |
| WLED reachable but DDP appears ignored | DDP/realtime disabled; wrong UDP port; LED count/output mismatch; WLED state off | Confirm UDP/4048, LED count/output settings, realtime state, and power | Compare the device with [WLED commissioning](commissioning/wled-controller.md), then repeat first light |
| Effect lights briefly and stops | One-shot frame; realtime timeout; finite duration; process error | Check whether the command used `--hold`, `--duration`, or `--loops` and read exit output | Use a held/finite loop or normal operation; inspect [DDP reference](reference/wled-and-ddp.md#one-shot-versus-held-output) |
| Wrong colours | RGB/colour-order setting; frame colour assumption; wiring | Run the controller-colour test and compare WLED output order | Verify WLED colour order against its export/device, not by changing route data |
| Correct colours on wrong strings | Physical data path swapped; local config host mapping wrong | Run `ddp-all controller-colors` and record colour-to-string observations | Correct the physical/controller mapping; do not alter `string_id` to conceal wiring |
| Geometry looks wrong | Wrong geometry/routes/positions set; camera view; stale generated data | Run geometry/route/position validation and reset the simulator view | Regenerate positions and use [geometry](geometry.md); do not reshape coordinates in the browser |
| Control UI unavailable | Control service not running; port occupied; service is simulator-only; browser URL wrong | Check the service terminal and `curl -s http://127.0.0.1:8080/api/control/capabilities` | Follow [control service](control-service.md) and [REST reference](api-rest.md) |
| Live output unavailable in control service | Started without `--controllers`; missing `--allow-live-control`; request selected disabled mode | Read `live_ddp_available` and `supported_outputs` from capabilities | Restart deliberately with the required flags; keep bind host local |
| Effect/service unexpectedly stops | Sink/producer error; invalid data; Ctrl+C; worker cancellation | Read the final CLI error and `/api/runtime/status` `latest_error`/`latest_sink_error` | Fix the named sink/data issue; do not start a competing worker |
| Factory-reset/replacement WLED controller | Address, LED count, output, realtime, or power/current settings lost | Compare the device with its matching public export | Follow [WLED controller commissioning](commissioning/wled-controller.md), then first light |

## Safety stops

- If geometry, route, or positions validation fails: **stop before effects**.
- If the simulator checkpoint has not passed: **stop before physical DDP**.
- If controller allocation validation fails: **stop before WLED reads or DDP**.
- If a physical power/current setting is unknown: **stop before brightness `255`** and obtain the missing installation fact.
- If a string identity is wrong: **stop normal operation** and correct wiring/configuration through the authorised physical process.

## What this component cannot prove

The software can validate file structure and prepare frames. It cannot prove electrical safety, PSU/fuse condition, physical data wiring, current draw, radio conditions, router state, or that a public export is still the device's live configuration. Those facts must be checked on the installation. Missing controller-host, router/AP, and physical power-off details are listed in [source of truth](reference/source-of-truth.md#facts-not-currently-captured).
