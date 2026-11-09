# Modelos de prompt para o Codex

O Codex roda em segundo plano, sem interação, chamado pelo Claude:

```powershell
Get-Content prompt.md -Raw | codex exec -C <pasta> -s workspace-write -o resposta.md -
```

## Imagens

```
GERE AS IMAGENS do anúncio descrito em ANUNCIO.md.
Produto: <peças, tamanho aproximado, CORES EXATAS POR PARTE — diga o que muda em relação à foto de referência>.
Referências (baixe e inspecione antes de gerar): <URLs ou caminhos; a foto real tem prioridade>.
Salve em ./imagens/ (PNG 1:1, ≥ 1024 px): 01_capa, 02_ambientada, 03... (uma por opção/kit).
Regras: manter a silhueta, as proporções, a geometria e o acabamento real da impressão (não esconder as linhas de camada);
sem texto, logo, medidas ou contatos; sem luz, movimento, acessórios ou funções inventadas;
objetos de cenário só na imagem ambientada; compare com a referência e refaça se distorcer.
NÃO publique nada.
No fim, escreva ./imagens/RELATORIO_IMAGENS.md (função de cada imagem + diferenças a conferir).
```

## Revisão cruzada

```
Você é revisor. NÃO edite arquivos existentes; escreva só ./REVISAO_CODEX.md.
Revise ANUNCIO.md, CUSTO_PRODUCAO.md e GUIA_PRECIFICACAO.md.
1) Refaça todas as contas a partir de: <pesos, tempos, R$/kg, fórmulas, cenários>.
2) Aponte informação inventada ou não confirmada e inconsistências entre título, descrição e variações;
   sugira até 3 títulos melhores para a busca da Shopee (< 100 caracteres).
3) Riscos: taxas da Shopee na opção mais barata; licença comercial do modelo 3D.
Formato: OK / PROBLEMA / SUGESTÃO, com o trecho exato.
```
