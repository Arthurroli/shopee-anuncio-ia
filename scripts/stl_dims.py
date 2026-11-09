"""Mede dimensões (mm) e volume (cm3) de STL binário. Uso: python -I stl_dims.py a.stl [b.stl ...]
As medidas são do ARQUIVO em escala 100% — não são a medida final da peça impressa/montada.
O volume só é confiável se a malha for fechada."""
import math, struct, sys
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')

for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    if len(d) < 84:
        print(f'{p}: arquivo pequeno demais para STL'); continue
    n = struct.unpack('<I', d[80:84])[0]
    if n == 0 or 84 + n * 50 != len(d):
        print(f'{p}: não é STL binário válido (pode ser ASCII) — medir no Orca'); continue
    lo = [math.inf] * 3; hi = [-math.inf] * 3; vol = 0.0
    for i in range(n):
        a = struct.unpack_from('<9f', d, 84 + i * 50 + 12)
        if not all(math.isfinite(x) for x in a):
            continue
        for k in range(3):
            for v in (a[k], a[k + 3], a[k + 6]):
                lo[k] = min(lo[k], v); hi[k] = max(hi[k], v)
        x1, y1, z1, x2, y2, z2, x3, y3, z3 = a
        vol += (x1 * (y2 * z3 - y3 * z2) - x2 * (y1 * z3 - y3 * z1) + x3 * (y1 * z2 - y2 * z1)) / 6
    if not all(math.isfinite(x) for x in lo + hi):
        print(f'{p}: sem coordenadas válidas'); continue
    print(f'{p}: X {hi[0]-lo[0]:.1f} × Y {hi[1]-lo[1]:.1f} × Z {hi[2]-lo[2]:.1f} mm | volume (se malha fechada) {abs(vol)/1000:.1f} cm3')
