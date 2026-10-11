# engine_runner.py
# Entry point para PyInstaller — executa o engine de vídeo (engine.py).
# O GUI chama este executável como subprocess quando está frozen.
import runpy
runpy.run_module("engine", run_name="__main__", alter_sys=True)
