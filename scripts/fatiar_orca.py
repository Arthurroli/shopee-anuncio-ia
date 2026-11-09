"""Fatia STL/3MF no OrcaSlicer pela linha de comando e devolve peso e tempo.

Uso:
  python -I fatiar_orca.py --stl "peca.stl|projeto.3mf" --nome cruz --saida "<pasta>" \
      [--impressora ad5x|a1mini] [--material petg|pla] [--preco-kg 75] \
      [--paredes 3] [--infill 15] [--padrao gyroid] [--camada 0.2] \
      [--suporte nenhum|arvore|normal] [--brim auto|nenhum|externo|orelha] \
      [--manter-config] [--mesa N]

--manter-config: para 3MF JÁ configurado pelo Arthur (Bambu Studio/Orca) — fatia com a impressora/processo/
  filamento salvos no próprio arquivo (só troca o R$/kg e o que for passado explicitamente). Preferir este modo
  quando o 3MF é dele: reflete o que ele imprime de verdade (e o material vem do arquivo, não de --material).
--mesa N: fatia só a mesa N (0 = todas). Com várias mesas, PERGUNTAR se são peças do mesmo conjunto (somar)
  ou versões alternativas do produto (fatiar cada uma separada).

Sem --manter-config: aplica os perfis de SISTEMA do Orca (a CLI recusa perfis de usuário):
 1) fatia com os JSON de sistema e exporta um 3MF;  2) edita Metadata/project_settings.config com as opções
 pedidas;  3) fatia de novo e lê peso/tempo no cabeçalho de cada plate_N.gcode.
3MF do Bambu Studio pode trazer valores que o Orca rejeita (ex.: -1): o script ajusta ao limite mínimo e avisa.
Saída: <saida>/<nome>_fatiado.3mf + linha JSON.
Limites: é estimativa do fatiador; perfis genéricos precisam de calibração; não valida encaixes.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, zipfile
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')

ORCA = r'C:\Program Files\OrcaSlicer\orca-slicer.exe'
PROF = r'C:\Program Files\OrcaSlicer\resources\profiles'
PERFIS = {
    ('ad5x', 'petg'): ('Flashforge', 'Flashforge AD5X 0.4 nozzle', '0.20mm Standard @FF AD5X', 'Flashforge Generic PETG'),
    ('ad5x', 'pla'):  ('Flashforge', 'Flashforge AD5X 0.4 nozzle', '0.20mm Standard @FF AD5X', 'Flashforge PLA Basic @FF AD5X'),
    ('a1mini', 'petg'): ('BBL', 'Bambu Lab A1 mini 0.4 nozzle', '0.20mm Standard @BBL A1M', 'Generic PETG @BBL A1M'),
    ('a1mini', 'pla'):  ('BBL', 'Bambu Lab A1 mini 0.4 nozzle', '0.20mm Standard @BBL A1M', 'Generic PLA @BBL A1M'),
}
DENS = {'petg': 1.27, 'pla': 1.24}  # só usado se o perfil vier sem densidade
SUPORTE = {'nenhum': {'enable_support': '0'},
           'arvore': {'enable_support': '1', 'support_type': 'tree(auto)', 'support_style': 'tree_slim'},
           'normal': {'enable_support': '1', 'support_type': 'normal(auto)'}}
BRIM = {'auto': 'auto_brim', 'nenhum': 'no_brim', 'externo': 'outer_only', 'orelha': 'brim_ears'}
UNID = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}


def falha(msg, r=None):
    extra = ('\n' + (r.stdout + r.stderr)[-800:]) if r is not None else ''
    sys.exit('ERRO: ' + msg + extra)


def run(args):
    return subprocess.run([ORCA] + args, capture_output=True, text=True, errors='replace')


def tempo_em_s(t):
    partes = re.findall(r'(\d+)\s*([dhms])', t)
    if not partes or re.sub(r'[\d\sdhms]', '', t):
        falha(f'formato de tempo não reconhecido: {t!r}')
    s = sum(int(n) * UNID[u] for n, u in partes)
    if s <= 0: falha(f'tempo zero/inválido: {t!r}')
    return s


def ler_gcode(path, dens):
    txt = open(path, errors='replace').read()
    mg = re.search(r'total filament used \[g\] = ([\d.]+)', txt)
    estimado = False
    if mg and float(mg.group(1)) > 0:
        peso = float(mg.group(1))
    else:
        mc = re.search(r'filament used \[cm3\] = ([\d.,\s]+)', txt)
        if not mc: falha(f'peso não encontrado em {path}')
        vols = [float(x) for x in re.findall(r'[\d.]+', mc.group(1))]
        peso = sum(vols) * dens; estimado = True
    mt = re.search(r'estimated printing time \(normal mode\) = ([^\n]+)', txt) or re.search(r'total estimated time: ([^\n;]+)', txt)
    if not mt: falha(f'tempo não encontrado em {path}')
    return peso, tempo_em_s(mt.group(1).strip()), estimado


def ler_3mf(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def gravar_3mf(files, path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n, d in files.items(): zo.writestr(n, d)


def fatiar_com_correcao(files, c, tmp, nome, args_antes, args_depois, corrigidos):
    """Grava o 3MF com a config c e fatia; se o Orca recusar valores, ajusta ao mínimo e tenta de novo (até 5x)."""
    entrada = os.path.join(tmp, nome + '_in.3mf'); out = os.path.join(tmp, nome + '_out')
    r = None
    for _ in range(5):
        files['Metadata/project_settings.config'] = json.dumps(c, indent=1).encode()
        gravar_3mf(files, entrada)
        shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
        r = run(args_antes + ['--allow-newer-file', '--outputdir', out] + args_depois + [entrada])
        ruins = re.findall(r'(\w+): (-?[\d.]+) not in range \[(-?[\d.]+),', r.stdout + r.stderr)
        if r.returncode == 0 or not ruins:
            return r, out
        for k, v, lo in ruins:
            novo = lo.rstrip('0').rstrip('.') if '.' in lo else lo
            c[k] = [novo] * len(c[k]) if isinstance(c.get(k), list) else novo
            corrigidos[k] = f'{v} -> {novo}'
    return r, out


def resolver(vend, tipo, nome):
    """Lê um perfil de sistema do Orca resolvendo a cadeia 'inherits'."""
    p = os.path.join(PROF, vend, tipo, nome + '.json')
    if not os.path.exists(p): falha('perfil não encontrado: ' + p)
    d = json.load(open(p, encoding='utf8'))
    r = resolver(vend, tipo, d['inherits']) if d.get('inherits') else {}
    r.update(d)
    return r


def densidade(c, material):
    try:
        d = float((c.get('filament_density') or ['0'])[0])
        if d > 0: return d
    except (ValueError, TypeError):
        pass
    tipo = str((c.get('filament_type') or [material])[0]).lower()
    return DENS['pla'] if 'pla' in tipo else DENS['petg'] if 'petg' in tipo else DENS[material]


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--stl', required=True); a.add_argument('--nome', required=True); a.add_argument('--saida', required=True)
    a.add_argument('--impressora', default='ad5x', choices=['ad5x', 'a1mini'])
    a.add_argument('--material', default='petg', choices=['petg', 'pla'])
    a.add_argument('--preco-kg', type=float, default=75.0)
    a.add_argument('--paredes', type=int); a.add_argument('--infill', type=float); a.add_argument('--padrao')
    a.add_argument('--camada', type=float)
    a.add_argument('--suporte', choices=list(SUPORTE)); a.add_argument('--brim', choices=list(BRIM))
    a.add_argument('--manter-config', action='store_true')
    a.add_argument('--mesa', type=int, default=0)
    o = a.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', o.nome): falha('--nome só aceita letras, números, _ e -')
    if o.preco_kg <= 0 or o.mesa < 0 or (o.paredes is not None and o.paredes < 1) \
            or (o.infill is not None and not 0 <= o.infill <= 100) or (o.camada is not None and not 0.04 <= o.camada <= 0.6):
        falha('valor numérico fora da faixa')
    if not os.path.exists(o.stl): falha('não encontrado: ' + o.stl)
    e3mf = o.stl.lower().endswith('.3mf')
    if o.manter_config and not e3mf: falha('--manter-config só vale para arquivo .3mf')
    os.makedirs(o.saida, exist_ok=True)
    final = os.path.join(o.saida, f'{o.nome}_fatiado.3mf')
    tmp = tempfile.mkdtemp(prefix='orca_')
    corrigidos = {}
    try:
        if o.manter_config:
            files = ler_3mf(o.stl)
        else:
            vend, maq, proc, fil = PERFIS[(o.impressora, o.material)]
            m = os.path.join(PROF, vend, 'machine', maq + '.json')
            p = os.path.join(PROF, vend, 'process', proc + '.json')
            f = os.path.join(PROF, vend, 'filament', fil + '.json')
            for x in (m, p, f):
                if not os.path.exists(x): falha('perfil não encontrado: ' + x)
            perfis = ['--load-settings', m + ';' + p, '--load-filaments', f]
            if e3mf:  # 3MF de outro programa: corrigir valores inválidos antes de aplicar os perfis do sistema
                fi = ler_3mf(o.stl)
                ci = json.loads(fi['Metadata/project_settings.config'])
                r, out1 = fatiar_com_correcao(fi, ci, tmp, 'p1', ['--slice', '0'], ['--export-3mf', 'base.3mf'] + perfis, corrigidos)
            else:
                out1 = os.path.join(tmp, 'p1_out'); os.makedirs(out1)
                r = run(['--slice', '0', '--allow-newer-file', '--outputdir', out1, '--export-3mf', 'base.3mf'] + perfis + [o.stl])
            base = os.path.join(out1, 'base.3mf')
            if r.returncode != 0 or not os.path.exists(base): falha('passo 1 (fatiamento base) falhou', r)
            files = ler_3mf(base)
        c = json.loads(files['Metadata/project_settings.config'])
        if not o.manter_config:
            # A CLI só troca o slot 1 e, com 3MF, mantém processo/filamentos do arquivo. Forçar o perfil de sistema
            # completo: processo inteiro + filamento escolhido em TODOS os slots (a peça pode usar o slot 2, 3...).
            pp = resolver(vend, 'process', proc); fp = resolver(vend, 'filament', fil)
            meta = {'name', 'inherits', 'from', 'setting_id', 'instantiation', 'type', 'version', 'compatible_printers',
                    'compatible_printers_condition', 'compatible_prints', 'compatible_prints_condition', 'filament_id'}
            for k, v in pp.items():
                if k not in meta and k in c and isinstance(c[k], list) == isinstance(v, list):
                    c[k] = v
            nslots = len(c.get('filament_type', [None]))
            for k, v in fp.items():
                if k in meta or k not in c or not isinstance(c[k], list): continue
                val = v[0] if isinstance(v, list) and v else v
                c[k] = [val] * nslots
            c['filament_settings_id'] = [fil] * nslots
            c['print_settings_id'] = proc
        ov = {}
        if o.paredes is not None: ov['wall_loops'] = str(o.paredes)
        if o.infill is not None: ov['sparse_infill_density'] = f'{o.infill:g}%'
        if o.padrao: ov['sparse_infill_pattern'] = o.padrao
        if o.camada is not None: ov['layer_height'] = ov['initial_layer_print_height'] = f'{o.camada:g}'
        if o.suporte: ov.update(SUPORTE[o.suporte])
        if o.brim: ov['brim_type'] = BRIM[o.brim]
        c.update(ov)
        c['filament_cost'] = [f'{o.preco_kg:g}'] * len(c.get('filament_cost', ['x']))
        info = {k: c.get(k) for k in ('printer_settings_id', 'print_settings_id', 'filament_settings_id', 'filament_type',
                                       'layer_height', 'wall_loops', 'sparse_infill_density', 'enable_support')}
        files = {n: d for n, d in files.items() if not n.endswith(('.gcode', '.md5'))}
        r, out = fatiar_com_correcao(files, c, tmp, 'p2', ['--slice', str(o.mesa)], ['--export-3mf', 'f.3mf'], corrigidos)
        gs = sorted(x for x in os.listdir(out) if x.endswith('.gcode'))
        if r.returncode != 0 or not gs or not os.path.exists(os.path.join(out, 'f.3mf')): falha('passo 2 (fatiamento final) falhou', r)
        dens = densidade(c, o.material)
        mesas = []
        for g in gs:
            peso, seg, est = ler_gcode(os.path.join(out, g), dens)
            mesas.append({'mesa': g, 'peso_g': round(peso, 3), 'tempo_s': seg, 'peso_estimado_por_volume': est})
        if os.path.exists(final): os.replace(final, final + '.anterior')
        shutil.copy(os.path.join(out, 'f.3mf'), final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    avisos = []
    if len(mesas) > 1:
        avisos.append('VÁRIAS MESAS: confirmar com o Arthur se são peças do MESMO conjunto (somar) ou versões alternativas '
                      '(fatiar com --mesa N).')
    if e3mf and not o.manter_config:
        avisos.append('3MF + perfil de sistema: o Orca troca impressora/filamento mas MANTÉM o processo gravado no 3MF '
                      '(camada, paredes, preenchimento...). Para 3MF do Arthur usar --manter-config; para mudar processo, '
                      'passar --camada/--paredes/--infill explicitamente.')
    aviso = ' | '.join(avisos)
    print(json.dumps({'nome': o.nome, 'modo': 'config do 3MF' if o.manter_config else f'perfil sistema {o.impressora}/{o.material}',
                      'preco_kg': o.preco_kg, 'densidade_usada': dens, 'peso_g': round(sum(x['peso_g'] for x in mesas), 3),
                      'tempo_s': sum(x['tempo_s'] for x in mesas), 'mesas': mesas, 'aviso': aviso, 'config_usada': info,
                      'config_alterada': ov, 'valores_corrigidos_para_orca': corrigidos, '3mf': final}, ensure_ascii=False))


if __name__ == '__main__':
    main()
