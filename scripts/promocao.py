"""Preço âncora + Oferta Relâmpago + cupom — método do Arthur (conversa "Calculadora de precificação", ChatGPT).

Método (definitivo na conversa): desconto normal NÃO acumula com a relâmpago; cupom aplicado DEPOIS da relâmpago.
  preço na relâmpago = âncora × (1 − relâmpago)
  preço final        = preço na relâmpago − cupom
  âncora             = (preço final desejado + cupom) / (1 − relâmpago)
Lucro (hipótese da conversa, NÃO verificada no Seller Center):
  comissão = base × comissão%  (base padrão = preço final pago, após cupom)
  líquido  = preço final − comissão − taxa fixa
  lucro    = líquido − custo
  preço mínimo sem prejuízo = (custo + taxa fixa) / (1 − comissão%)
  preço final para um lucro desejado = (custo + lucro + taxa fixa) / (1 − comissão%)

Uso (um --item por opção/kit; campos: final, ancora, lucro, custo):
  python -I promocao.py --item "1 un|final=22.50|custo=7" --item "Kit 2|final=39.90|custo=14"
  python -I promocao.py --item "1 un|lucro=7|custo=7"        (calcula o preço final pelo lucro desejado)
  python -I promocao.py --item "1 un|ancora=34.90|custo=7"   (testa uma âncora arredondada)
Parâmetros: --relampago 25 --cupom 3 --comissao 20 --taxa-fixa 4 --base-comissao final|relampago
  (padrões = valores usados na conversa; comissão e taxa fixa são SUPOSIÇÃO — conferir a tabela atual da Shopee).
"""
import argparse, sys
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_CEILING
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
C = D('0.01')


def r2(x): return x.quantize(C, ROUND_HALF_UP)


def ancora_comercial(x):
    """Próximo valor terminado em ,90 >= x (sugestão comercial; muda o preço final)."""
    inteiro = x.to_integral_value(ROUND_CEILING) if x != x.to_integral_value() else x
    cand = inteiro - 1 + D('0.90')
    return cand if cand >= x else inteiro + D('0.90')


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--item', action='append', required=True)
    a.add_argument('--relampago', type=D, default=D('25')); a.add_argument('--cupom', type=D, default=D('3'))
    a.add_argument('--comissao', type=D, default=D('20')); a.add_argument('--taxa-fixa', type=D, default=D('4'))
    a.add_argument('--base-comissao', choices=['final', 'relampago'], default='final')
    o = a.parse_args()
    def valor(v, onde):
        if not v.is_finite() or v < 0: sys.exit(f'ERRO: valor inválido (negativo/NaN/infinito) em {onde}')
        if v != v.quantize(C): sys.exit(f'ERRO: use no máximo 2 casas decimais (centavos) em {onde}')
        return v
    itens = []
    for it in o.item:
        partes = it.split('|'); campos = {}
        for kv in partes[1:]:
            k, _, v = kv.partition('='); k = k.strip()
            if k not in ('final', 'ancora', 'lucro', 'custo'): sys.exit(f'ERRO: campo desconhecido em {it!r}')
            if k in campos: sys.exit(f'ERRO: campo {k} repetido em {it!r}')
            try: campos[k] = D(v.strip().replace(',', '.'))
            except Exception: sys.exit(f'ERRO: valor inválido em {it!r}')
            valor(campos[k], repr(it))
        modos = [m for m in ('final', 'ancora') if m in campos] + (['lucro'] if 'lucro' in campos else [])
        if len(modos) != 1: sys.exit(f'ERRO: item {it!r}: use UM modo — final, ancora ou lucro(+custo)')
        if 'lucro' in campos and 'custo' not in campos: sys.exit(f'ERRO: item {it!r}: lucro exige custo')
        itens.append((partes[0].strip(), campos))
    for nome in ('relampago', 'comissao'):
        x = getattr(o, nome)
        if not x.is_finite() or not 0 <= x < 100: sys.exit(f'ERRO: --{nome} deve estar entre 0 e 100')
    valor(o.cupom, '--cupom'); valor(o.taxa_fixa, '--taxa-fixa')
    rel = o.relampago / 100; com = o.comissao / 100
    # comissão sobre o preço na relâmpago (antes do cupom) acrescenta com×cupom ao que o preço final precisa cobrir
    extra_base = com * o.cupom if o.base_comissao == 'relampago' else D(0)
    print(f'Premissas: relâmpago {o.relampago}% (sem acumular com desconto normal) · cupom R$ {o.cupom} após a relâmpago · '
          f'comissão {o.comissao}% sobre preço {o.base_comissao} · taxa fixa R$ {o.taxa_fixa} por pedido  [comissão/taxa = SUPOSIÇÃO]')
    print('| Opção | Âncora exata | Âncora a cadastrar | Na relâmpago | Final pago | Comissão | Taxa fixa | Líquido | Custo | Lucro | Preço mínimo | Âncora ,90 sugerida → final |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|')
    for op, cp in itens:
        custo, final, anc, lucro = cp.get('custo'), cp.get('final'), cp.get('ancora'), cp.get('lucro')
        if lucro is not None:
            final = ((custo + lucro + o.taxa_fixa + extra_base) / (1 - com)).quantize(C, ROUND_CEILING)
        exata = (final + o.cupom) / (1 - rel) if final is not None else None
        cad = anc if anc is not None else r2(exata)
        na_rel = r2(cad * (1 - rel)); pago = na_rel - o.cupom
        if pago <= 0: sys.exit(f'ERRO: item {op}: cupom R$ {o.cupom} é maior ou igual ao preço na relâmpago (R$ {na_rel})')
        if final is not None and anc is None and pago != final:  # garante a meta depois dos arredondamentos
            cad = (exata).quantize(C, ROUND_CEILING); na_rel = r2(cad * (1 - rel)); pago = na_rel - o.cupom
        base = pago if o.base_comissao == 'final' else na_rel
        comis = r2(base * com); liq = pago - comis - o.taxa_fixa
        lucro_r = (liq - custo) if custo is not None else None
        minimo = ((custo + o.taxa_fixa + extra_base) / (1 - com)).quantize(C, ROUND_CEILING) if custo is not None else None
        if lucro is not None and lucro_r is not None and lucro_r < lucro:
            print(f'(aviso: {op} — após arredondamentos o lucro ficou R$ {lucro_r:.2f}, abaixo do desejado R$ {lucro:.2f})')
        sug = ancora_comercial(cad); sug_final = r2(sug * (1 - rel)) - o.cupom
        f = lambda x: '—' if x is None else f'R$ {x:.2f}'
        print(f'| {op} | {"—" if exata is None else f"{exata:.4f}"} | {f(cad)} | {f(na_rel)} | {f(pago)} | {f(comis)} | {f(o.taxa_fixa)} | '
              f'{f(liq)} | {f(custo)} | {f(lucro_r)} | {f(minimo)} | {f(sug)} → {f(sug_final)} |')
    print('\nAvisos: arredondamento do preço promocional, base da comissão, quem banca o cupom e taxa fixa por kit '
          'NÃO foram verificados no Seller Center. Preço final abaixo do "Preço mínimo" = prejuízo.')


if __name__ == '__main__':
    main()
