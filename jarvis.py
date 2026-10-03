import os
import re
import queue
import threading
import subprocess
import webbrowser
import unicodedata
import tempfile
import requests
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from urllib.parse import urlencode

import speech_recognition as sr
import pyttsx3
import ollama

NOME = "J.A.R.V.I.S"
MODELO_IA = "qwen3:4b"

IDIOMA = "pt-BR"
TEMPERATURA = 0.7
CONTEXTO = 4096

COR_FUNDO = "#07111f"
COR_PAINEL = "#0b1b2d"
COR_DESTAQUE = "#00d9ff"
COR_TEXTO = "#d7f5ff"
COR_SECUNDARIA = "#7da8bd"

eventos = queue.Queue()
fila_voz = queue.Queue()

reconhecedor = sr.Recognizer()

escutando = True
janela_minimizada = False

APLICATIVOS = {
    "calculadora": "calc.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "pintura": "mspaint.exe",
    "explorador": "explorer.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "prompt de comando": "cmd.exe",
    "powershell": "powershell.exe",
}

PASTAS = {
    "downloads": "Downloads",
    "documentos": "Documents",
    "imagens": "Pictures",
    "fotos": "Pictures",
    "videos": "Videos",
    "músicas": "Music",
    "musicas": "Music",
    "área de trabalho": "Desktop",
    "area de trabalho": "Desktop",
    "desktop": "Desktop",
}

def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto

def adicionar_log(remetente, mensagem):
    horario = datetime.now().strftime("%H:%M:%S")

    caixa_log.configure(state="normal")
    caixa_log.insert(tk.END, f"[{horario}] ", "hora")
    caixa_log.insert(tk.END, f"{remetente}: ", "remetente")
    caixa_log.insert(tk.END, f"{mensagem}\n\n", "mensagem")
    caixa_log.configure(state="disabled")
    caixa_log.see(tk.END)

def atualizar_interface():
    try:
        while True:
            remetente, mensagem = eventos.get_nowait()
            adicionar_log(remetente, mensagem)
    except queue.Empty:
        pass

    janela.after(100, atualizar_interface)

def minimizar_janela():
    janela.iconify()

def enviar_mensagem(event=None):
    mensagem = entrada.get().strip()

    if not mensagem:
        return

    entrada.delete(0, tk.END)
    adicionar_log("Você", mensagem)

    threading.Thread(
        target=processar_comando,
        args=(mensagem,),
        daemon=True
    ).start()

def ao_fechar():
    global escutando
    escutando = False
    janela.destroy()

def trabalhador_voz():
    motor = pyttsx3.init()
    motor.setProperty("rate", 175)
    motor.setProperty("volume", 1.0)

    try:
        vozes = motor.getProperty("voices")

        for voz in vozes:
            dados = normalizar(
                voz.name + " " + str(voz.id)
            )

            if any(
                termo in dados
                for termo in [
                    "brazil",
                    "portuguese",
                    "brasil",
                    "daniel",
                    "antonio",
                    "ricardo"
                ]
            ):
                motor.setProperty("voice", voz.id)
                break
    except Exception:
        pass

    while True:
        mensagem = fila_voz.get()

        if mensagem is None:
            break

        try:
            motor.say(mensagem)
            motor.runAndWait()
        except Exception as erro:
            eventos.put(("Sistema", f"Erro na voz: {erro}"))

def falar(mensagem):
    eventos.put((NOME, mensagem))
    fila_voz.put(mensagem)

def abrir_aplicativo(nome):
    nome = normalizar(nome)

    if nome in APLICATIVOS:
        try:
            subprocess.Popen(APLICATIVOS[nome], shell=True)
            falar(f"Abrindo {nome}.")
            return True
        except Exception as erro:
            falar(f"Não consegui abrir {nome}: {erro}")
            return True

    return False

def abrir_pasta(nome):
    nome = normalizar(nome)

    if nome in PASTAS:
        pasta = PASTAS[nome]
        caminho = os.path.join(
            os.path.expanduser("~"),
            pasta
        )

        if os.path.isdir(caminho):
            try:
                os.startfile(caminho)
                falar(f"Abrindo a pasta {nome}.")
            except Exception as erro:
                falar(f"Erro ao abrir a pasta: {erro}")
        else:
            falar(f"Não encontrei a pasta {nome}.")

        return True

    return False

def abrir_site(nome):
    nome = normalizar(nome)

    sites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "chatgpt": "https://chatgpt.com",
        "roblox": "https://www.roblox.com",
    }

    if nome in sites:
        webbrowser.open(sites[nome])
        falar(f"Abrindo {nome}.")
        return True

    return False

def pesquisar_google(termo):
    termo = termo.strip()

    if not termo:
        falar("O que você deseja pesquisar?")
        return

    url = "https://www.google.com/search?" + urlencode({
        "q": termo
    })

    webbrowser.open(url)
    falar(f"Pesquisando por {termo}.")

def perguntar_ia(pergunta):
    try:
        resultado = ollama.chat(
            model=MODELO_IA,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é JARVIS, um assistente virtual "
                        "inspirado em uma inteligência artificial "
                        "de ficção científica. Responda em português "
                        "do Brasil, de forma natural, educada e "
                        "objetiva. Você está rodando localmente. "
                        "Não diga que executou ações no computador "
                        "se elas não foram realmente executadas."
                    )
                },
                {
                    "role": "user",
                    "content": pergunta
                }
            ],
            options={
                "num_ctx": CONTEXTO,
                "temperature": TEMPERATURA
            }
        )

        resposta = resultado["message"]["content"].strip()

        if not resposta:
            return "Não consegui formular uma resposta."

        return resposta

    except Exception as erro:
        return (
            "Não consegui acessar a inteligência artificial local. "
            "Verifique se o Ollama está aberto e se o modelo "
            f"{MODELO_IA} está instalado. Detalhes: {erro}"
        )

def remover_palavra_inicial(texto, palavras):
    texto_normalizado = normalizar(texto)

    for palavra in palavras:
        palavra_normalizada = normalizar(palavra)

        if texto_normalizado.startswith(palavra_normalizada + " "):
            return texto[len(palavra):].strip()

        if texto_normalizado == palavra_normalizada:
            return ""

    return texto.strip()

def processar_comando(comando):
    comando_original = comando.strip()
    comando_limpo = normalizar(comando_original)

    if not comando_limpo:
        return

    if comando_limpo in [
        "sair",
        "fechar jarvis",
        "desligar jarvis",
        "encerrar"
    ]:
        falar("Até logo.")
        return

    if comando_limpo in [
        "que horas sao",
        "diga as horas",
        "horas"
    ]:
        hora = datetime.now().strftime("%H:%M")
        falar(f"Agora são {hora}.")
        return

    if comando_limpo in [
        "que dia e hoje",
        "qual a data",
        "diga a data"
    ]:
        data = datetime.now().strftime("%d/%m/%Y")
        falar(f"Hoje é {data}.")
        return

    if comando_limpo in [
        "minimizar",
        "minimizar janela",
        "esconder janela"
    ]:
        janela.after(0, minimizar_janela)
        falar("Minimizando a janela.")
        return

    comandos_abrir = [
        "abrir",
        "abra",
        "abre",
        "iniciar",
        "inicie",
        "executar"
    ]

    alvo = remover_palavra_inicial(
        comando_original,
        comandos_abrir
    )

    if alvo != comando_original:
        alvo_normalizado = normalizar(alvo)

        alvo_normalizado = re.sub(
            r"^(o|a|os|as|meu|minha)\s+",
            "",
            alvo_normalizado
        ).strip()

        if abrir_aplicativo(alvo_normalizado):
            return

        if abrir_pasta(alvo_normalizado):
            return

        if abrir_site(alvo_normalizado):
            return

        falar(
            f"Não encontrei o programa ou pasta {alvo}. "
            "Vou tentar entender seu pedido."
        )

    comandos_pesquisa = [
        "pesquisar por",
        "pesquise por",
        "pesquisar",
        "pesquise",
        "buscar por",
        "busque por",
        "procure por",
        "procurar por"
    ]

    termo = remover_palavra_inicial(
        comando_original,
        comandos_pesquisa
    )

    if termo != comando_original:
        pesquisar_google(termo)
        return

    resposta = perguntar_ia(comando_original)
    falar(resposta)

def callback_microfone(reconhecedor, audio):
    if not escutando:
        return

    try:
        texto = reconhecedor.recognize_google(
            audio,
            language=IDIOMA
        )

        texto_normalizado = normalizar(texto)

        eventos.put(("Você (voz)", texto))

        if "jarvis" in texto_normalizado:
            comando = re.sub(
                r"\bjarvis\b",
                "",
                texto_normalizado,
                flags=re.IGNORECASE
            ).strip(" ,.!?")

            if comando:
                threading.Thread(
                    target=processar_comando,
                    args=(comando,),
                    daemon=True
                ).start()
            else:
                falar("Sim, estou ouvindo.")

    except sr.UnknownValueError:
        pass
    except sr.RequestError:
        eventos.put((
            "Sistema",
            "Não foi possível acessar o reconhecimento de voz. "
            "Verifique sua conexão com a internet."
        ))
    except Exception as erro:
        eventos.put(("Sistema", f"Erro no microfone: {erro}"))

def iniciar_microfone():
    global escutando

    try:
        microfone = sr.Microphone()

        with microfone as fonte:
            eventos.put((
                "Sistema",
                "Calibrando o microfone. Aguarde..."
            ))
            reconhecedor.adjust_for_ambient_noise(
                fonte,
                duration=1
            )

        eventos.put((
            "Sistema",
            "Microfone ativo. Diga 'Jarvis' para começar."
        ))

        parar = reconhecedor.listen_in_background(
            microfone,
            callback_microfone,
            phrase_time_limit=8
        )

        while escutando:
            threading.Event().wait(0.5)

        parar(wait_for_stop=False)

    except Exception as erro:
        eventos.put((
            "Sistema",
            "Não consegui iniciar o microfone. "
            f"Verifique o dispositivo e o PyAudio. Detalhes: {erro}"
        ))

janela = tk.Tk()
janela.title("J.A.R.V.I.S | Assistente")
janela.geometry("800x600")
janela.minsize(600, 450)
janela.configure(bg=COR_FUNDO)
janela.protocol("WM_DELETE_WINDOW", ao_fechar)

cabecalho = tk.Frame(
    janela,
    bg=COR_PAINEL,
    height=90
)
cabecalho.pack(fill="x")
cabecalho.pack_propagate(False)

titulo = tk.Label(
    cabecalho,
    text="J.A.R.V.I.S",
    font=("Segoe UI", 25, "bold"),
    fg=COR_DESTAQUE,
    bg=COR_PAINEL
)
titulo.pack(pady=(12, 0))

subtitulo = tk.Label(
    cabecalho,
    text="SISTEMA DE INTELIGÊNCIA ARTIFICIAL LOCAL",
    font=("Segoe UI", 9),
    fg=COR_SECUNDARIA,
    bg=COR_PAINEL
)
subtitulo.pack()

corpo = tk.Frame(
    janela,
    bg=COR_FUNDO,
    padx=18,
    pady=15
)
corpo.pack(fill="both", expand=True)

status = tk.Label(
    corpo,
    text="SISTEMA INICIALIZANDO",
    font=("Segoe UI", 10, "bold"),
    fg=COR_DESTAQUE,
    bg=COR_FUNDO,
    anchor="w"
)
status.pack(fill="x", pady=(0, 10))

caixa_log = scrolledtext.ScrolledText(
    corpo,
    wrap=tk.WORD,
    font=("Consolas", 10),
    bg=COR_PAINEL,
    fg=COR_TEXTO,
    insertbackground=COR_DESTAQUE,
    relief="flat",
    padx=12,
    pady=12,
    state="disabled"
)
caixa_log.pack(fill="both", expand=True)

caixa_log.tag_config(
    "hora",
    foreground=COR_SECUNDARIA
)
caixa_log.tag_config(
    "remetente",
    foreground=COR_DESTAQUE,
    font=("Consolas", 10, "bold")
)
caixa_log.tag_config(
    "mensagem",
    foreground=COR_TEXTO
)

linha_entrada = tk.Frame(
    corpo,
    bg=COR_FUNDO
)
linha_entrada.pack(fill="x", pady=(12, 0))

entrada = tk.Entry(
    linha_entrada,
    font=("Segoe UI", 12),
    bg=COR_PAINEL,
    fg=COR_TEXTO,
    insertbackground=COR_DESTAQUE,
    relief="flat"
)
entrada.pack(
    side="left",
    fill="x",
    expand=True,
    ipady=12,
    padx=(0, 8)
)
entrada.bind("<Return>", enviar_mensagem)

botao_enviar = tk.Button(
    linha_entrada,
    text="ENVIAR",
    font=("Segoe UI", 10, "bold"),
    bg=COR_DESTAQUE,
    fg="#00121c",
    activebackground="#74edff",
    relief="flat",
    padx=18,
    pady=10,
    command=enviar_mensagem
)
botao_enviar.pack(side="right")

rodape = tk.Frame(
    corpo,
    bg=COR_FUNDO
)
rodape.pack(fill="x", pady=(10, 0))

texto_modelo = tk.Label(
    rodape,
    text=f"IA LOCAL: {MODELO_IA}",
    font=("Segoe UI", 9),
    fg=COR_SECUNDARIA,
    bg=COR_FUNDO
)
texto_modelo.pack(side="left")

botao_minimizar = tk.Button(
    rodape,
    text="MINIMIZAR",
    font=("Segoe UI", 9),
    bg=COR_PAINEL,
    fg=COR_TEXTO,
    activebackground=COR_DESTAQUE,
    relief="flat",
    padx=12,
    command=minimizar_janela
)
botao_minimizar.pack(side="right")

def atualizar_status_interface(mensagem):
    eventos.put(("Sistema", mensagem))
    janela.after(0, lambda: status.configure(text=mensagem))

def verificar_e_baixar_modelo():
    try:
        atualizar_status_interface("VERIFICANDO MODELO DE IA")
        modelos = [m['name'] for m in ollama.list()['models']]
        
        if not any(MODELO_IA in m for m in modelos):
            atualizar_status_interface(f"BAIXANDO MODELO {MODELO_IA} (AGUARDE)")
            subprocess.run(["ollama", "pull", MODELO_IA], check=True)
            atualizar_status_interface("MODELO BAIXADO COM SUCESSO")
        else:
            atualizar_status_interface("MODELO DE IA PRONTO")
            
    except Exception as erro:
        atualizar_status_interface(f"ERRO AO BAIXAR MODELO: {erro}")

def instalar_ollama_automaticamente():
    try:
        atualizar_status_interface("VERIFICANDO OLLAMA NO SISTEMA")
        try:
            ollama.list()
            atualizar_status_interface("OLLAMA JA ESTA ATIVO")
            verificar_e_baixar_modelo()
            finalizar_inicializacao()
            return
        except Exception:
            pass

        atualizar_status_interface("BAIXANDO O OLLAMA (AGUARDE)")
        url_instalador = "https://ollama.com/download/OllamaSetup.exe"
        caminho_temp = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
        
        resposta = requests.get(url_instalador, stream=True)
        with open(caminho_temp, "wb") as f:
            for bloco in resposta.iter_content(chunk_size=1024):
                if bloco:
                    f.write(bloco)
        
        atualizar_status_interface("INSTALANDO O OLLAMA EM SEGUNDO PLANO")
        subprocess.run([caminho_temp, "/VERYSILENT", "/NORESTART"], check=True)
        
        atualizar_status_interface("OLLAMA INSTALADO COM SUCESSO")
        verificar_e_baixar_modelo()
        finalizar_inicializacao()

    except Exception as erro:
        atualizar_status_interface(f"ERRO NA INSTALACAO DO OLLAMA: {erro}")

def finalizar_inicializacao():
    adicionar_log(
        "Sistema",
        "J.A.R.V.I.S iniciado."
    )
    adicionar_log(
        "Sistema",
        f"Modelo de IA configurado: {MODELO_IA}"
    )
    adicionar_log(
        "Sistema",
        "Digite um comando ou diga 'Jarvis' perto do microfone."
    )

    threading.Thread(
        target=trabalhador_voz,
        daemon=True
    ).start()

    threading.Thread(
        target=iniciar_microfone,
        daemon=True
    ).start()

    atualizar_status_interface("SISTEMA ONLINE")

def iniciar_sistema():
    adicionar_log(
        "Sistema",
        "Iniciando verificação de dependências..."
    )

    threading.Thread(
        target=instalar_ollama_automaticamente,
        daemon=True
    ).start()

janela.after(500, iniciar_sistema)
janela.after(100, atualizar_interface)
janela.mainloop()
