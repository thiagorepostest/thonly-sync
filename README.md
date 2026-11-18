# Thonly Lyric Studio (Versão Local com Whisper large-v3)

Pacote para rodar o **Thonly Lyric Studio** 100% localmente no seu computador com **faster-whisper (`large-v3`)** e alinhamento **verso a verso**.

## Pré-requisitos
1. **Python 3.10+** instalado ([python.org/downloads](https://www.python.org/downloads/)).
2. **FFmpeg** instalado no sistema.

## Como iniciar
- **Windows:** dê dois cliques em `iniciar_windows.bat`.
- **Mac / Linux:** abra o terminal na pasta e rode:
  ```bash
  chmod +x iniciar_mac_linux.sh
  ./iniciar_mac_linux.sh
  ```

## Fluxo recomendado (substituindo erros automaticamente)
1. Carregue seu vídeo em **+ Vídeo**.
2. Na aba **Letra & .SRT**, cole a letra oficial da música (1 verso por linha).
3. Clique em **Transcrever / Sincronizar Versos**: o `large-v3` lê o áudio, encontra o tempo exato de cada palavra e já coloca **os seus versos colados** na tela, substituindo qualquer palavra errada.
