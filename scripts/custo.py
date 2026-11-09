"""Custo de produção pela regra da planilha "Financeiro Impressão 3D".

Uso: python -I custo.py pecas.json
pecas.json = {
  "pecas": {"cruz": {"g": 6.55, "s": 1682, "kg": 75}, "veu": {"g": 8.38, "s": 3566, "kg": 75}},
  "opcoes": {"Cruz": ["cruz", "veu"]},
  "cenarios": [{"nome": "A sem embalagem/ADS", "emb": 0, "ads": 0},
               {"nome": "B SIMULAÇÃO emb 0,29 + ADS 10%", "emb": 0.29, "ads": 0.10}]
}
g = gramas fatiadas, s = segundos, kg = R$/kg do filamento daquela peça.
Regras: material = g/1000*kg; energia = h*0,13*1,09; amortização = h*0,25;
produção = (material+energia+amortização+embalagem)*1,15*(1+ADS)  [embalagem UMA vez por opção];
venda = produção*3 arredondada para cima (só no final); lucro bruto = venda sem arredondar − produção (coluna N).
"""
import json, math, sys
from decimal import Decimal, ROUND_CEILING
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')


def erro(m): sys.exit('ERRO: ' + m)


d = json.load(open(sys.argv[1], encoding='utf8'))
pc = {}
for k, v in d.get('pecas', {}).items():
    for campo in ('g', 's', 'kg'):
        x = v.get(campo)
        if not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0: erro(f'peça {k}: {campo} inválido ({x})')
    h = v['s'] / 3600
    pc[k] = dict(g=v['g'], h=h, mat=v['g'] / 1000 * v['kg'], en=h * 13 * 1.09 / 100, am=2500 / 10000 * h)
if not d.get('opcoes'): erro('nenhuma opção definida')
for nome, ks in d['opcoes'].items():
    if not ks: erro(f'opção {nome} vazia')
    for k in ks:
        if k not in pc: erro(f'opção {nome}: peça {k} não existe em "pecas"')
for c in d.get('cenarios', [{'nome': 'sem embalagem/ADS', 'emb': 0, 'ads': 0}]):
    if c['emb'] < 0 or not 0 <= c['ads'] < 1: erro(f'cenário {c["nome"]}: embalagem/ADS inválidos')
    print(f"### {c['nome']}")
    print('| Opção | Peso | Horas | Produção | Venda ×3 | Venda arredondada | Lucro bruto |')
    print('|---|---:|---:|---:|---:|---:|---:|')
    for nome, ks in d['opcoes'].items():
        g = sum(pc[k]['g'] for k in ks); h = sum(pc[k]['h'] for k in ks)
        base = sum(pc[k]['mat'] + pc[k]['en'] + pc[k]['am'] for k in ks) + c['emb']
        prod = base * 1.15 * (1 + c['ads']); v = prod * 3
        # teto exato em Decimal; quantiza a 1e-9 só para descartar ruído binário do float
        vr = Decimal(repr(v)).quantize(Decimal('1e-9')).to_integral_value(rounding=ROUND_CEILING)
        print(f"| {nome} | {g:.2f} g | {h:.3f} | R$ {prod:.2f} | R$ {v:.2f} | R$ {vr} | R$ {v - prod:.2f} |")
    print()
