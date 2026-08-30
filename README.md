# Transcritor Windows V4 - TESTADO

Esta versão abandona o Nuitka, que apresentou AssertionError na compilação.

Agora usa PyInstaller ONEFILE.

O ponto principal é que o workflow:
1. instala dependências;
2. compila o EXE;
3. executa o próprio EXE com `--self-test`;
4. só publica o artefato se o EXE iniciar e importar:
   - requests
   - certifi
   - urllib3
   - idna
   - charset_normalizer
   - faster_whisper
   - ctranslate2
   - huggingface_hub
   - tokenizers
   - av
   - reportlab
   - tkinter

Artefato esperado:
`TranscritorAudio-Windows-V4-TESTADO`

Executável:
`TranscritorAudioV4.exe`
