# Quickstart

```bash
cd /workspace/thunderdome
python3 -m pip install -e .
python3 -m unittest discover -s controller/tests -v
thunderdome geometry validate
thunderdome controller info --host http://WLED_HOST
thunderdome ddp clear --host WLED_HOST
thunderdome ddp pixel --host WLED_HOST 0 --color FF0000 --brightness 32
thunderdome ddp range --host WLED_HOST 0 10 --color 00FF00 --brightness 32
```

HTTP/native effects and favorites are optional support functions, not the animation renderer.
