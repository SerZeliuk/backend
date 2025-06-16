## How to start the container 

Run 

```bash
docker compose up --build
```

*The backend is now listening on the port 5000:5000*

## How to run tests

In the main directory run 

```bash
python -m pytest --maxfail=1 --disable-warnings -q
```
Or just
```bash
pytest --maxfail=1 --disable-warnings -q
```
