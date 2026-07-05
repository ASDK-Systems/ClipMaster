import mlx_whisper
import inspect

print("MLX Whisper module contents:", dir(mlx_whisper))
if hasattr(mlx_whisper, "transcribe"):
    print("Transcribe signature:", inspect.signature(mlx_whisper.transcribe))
    print("Transcribe docstring:", mlx_whisper.transcribe.__doc__)
