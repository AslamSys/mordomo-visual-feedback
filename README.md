# 💡 Visual Feedback (LED Controller)

## 🔗 Navegação

**[🏠 AslamSys](https://github.com/AslamSys)** → **[📚 _system](https://github.com/AslamSys/_system)** → **[📂 Aslam (Orange Pi 5 16GB)](https://github.com/AslamSys/_system/blob/main/hardware/mordomo%20-%20(orange-pi-5-16gb)/README.md)** → **mordomo-visual-feedback**

### Containers Relacionados (mordomo)
- [mordomo-audio-bridge](https://github.com/AslamSys/mordomo-audio-bridge)
- [mordomo-tts-engine](https://github.com/AslamSys/mordomo-tts-engine)
- [mordomo-audio-capture-vad](https://github.com/AslamSys/mordomo-audio-capture-vad)
- [mordomo-wake-word-detector](https://github.com/AslamSys/mordomo-wake-word-detector)
- [mordomo-speaker-verification](https://github.com/AslamSys/mordomo-speaker-verification)
- [mordomo-whisper-asr](https://github.com/AslamSys/mordomo-whisper-asr)
- [mordomo-speaker-id-diarization](https://github.com/AslamSys/mordomo-speaker-id-diarization)
- [mordomo-source-separation](https://github.com/AslamSys/mordomo-source-separation)
- [mordomo-core-gateway](https://github.com/AslamSys/mordomo-core-gateway)
- [mordomo-orchestrator](https://github.com/AslamSys/mordomo-orchestrator)
- [mordomo-brain](https://github.com/AslamSys/mordomo-brain)
- [mordomo-system-watchdog](https://github.com/AslamSys/mordomo-system-watchdog)
- [mordomo-dashboard-ui](https://github.com/AslamSys/mordomo-dashboard-ui)
- [mordomo-openclaw-agent](https://github.com/AslamSys/mordomo-openclaw-agent)
- [mordomo-skills-runner](https://github.com/AslamSys/mordomo-skills-runner)

---

**Container:** `visual-feedback`  
**Ecossistema:** Mordomo  
**Posição no Fluxo:** Feedback Sensorial Passivo (Event Listener)

---

## 📋 Propósito

Controlador autônomo de feedback visual via LED Ring RGB programável (WS2812B). Traduz eventos do sistema em efeitos luminosos, proporcionando ao usuário uma compreensão imediata e intuitiva do estado do assistente de voz. Opera em modo híbrido: **NATS para eventos discretos** + **ZeroMQ stream para sincronização com TTS**.

---

## 🎯 Responsabilidades

### Primárias
- ✅ **Escutar eventos NATS** do sistema (wake word, conversação, processamento, erros)
- ✅ **Mapear eventos → efeitos visuais** (pulsação, fade, spinner, flash)
- ✅ **Controlar LED Ring WS2812B** via GPIO (12-16 LEDs)
- ✅ **Escutar stream ZeroMQ do TTS** para sincronização com voz (LED pulsa com amplitude)
- ✅ **Gerenciar prioridades** de eventos (erro sempre sobrescreve idle)

### Secundárias
- ✅ Configuração dinâmica via arquivo YAML (cores, efeitos, velocidades)
- ✅ Publicar métricas de uptime no NATS (`visual.feedback.status`)
- ✅ Suporte a múltiplas instâncias (LEDs em diferentes cômodos)

---

## 🏗️ Arquitetura Híbrida

### Sistema de Dois Canais

```
┌──────────────────────────────────────────────────────────────┐
│                    VISUAL FEEDBACK                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CANAL 1: Eventos Discretos (NATS)                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │  wake_word.detected → Flash + Fade Azul→Verde      │     │
│  │  speaker.verified → Verde sólido                   │     │
│  │  conversation.started → Verde breathing            │     │
│  │  brain.processing → Amarelo spinner               │     │
│  │  tts.speaking_started → Ativa Canal 2             │     │
│  │  tts.speaking_stopped → Desativa Canal 2          │     │
│  │  conversation.ended → Fade Verde→Azul             │     │
│  │  error.* → Vermelho piscando (prioridade máxima)  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  CANAL 2: ZeroMQ Stream (TTS Audio Sync)                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  1. Conecta no ZeroMQ do TTS Engine                │     │
│  │  2. Recebe chunks de áudio (streaming)             │     │
│  │  3. Calcula amplitude RMS a cada chunk             │     │
│  │  4. Mapeia amplitude (0.0-1.0) → Brilho (50-255)   │     │
│  │  5. LED pulsa no ritmo da fala do TTS              │     │
│  │                                                     │     │
│  │  Ativo apenas quando: tts.speaking_started         │     │
│  │  Desativa quando: tts.speaking_stopped             │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  OUTPUT: GPIO Pin 18 → WS2812B LED Ring (12-16 LEDs)        │
└──────────────────────────────────────────────────────────────┘
```

### Por que Híbrido?

- **NATS**: Perfeito para **quando** mudar de estado (idle → ouvindo → processando)
- **ZeroMQ Stream**: Perfeito para **como** sincronizar finamente (LED pulsa com volume da voz)
- **Resultado**: Aproveita infraestrutura existente, sem poluir NATS, sincronização perfeita (<5ms)

---

## 🎨 Mapeamento de Eventos → Efeitos

### Cores Contextuais (Baseado na Situação)

O **Brain/TTS** determina a cor base enviando o campo `context` junto com `tts.speaking_started`:

| Context Type | Cor Base (RGB) | Situação | Exemplo |
|--------------|----------------|----------|----------|
| `normal` | Verde (0,255,0) | Conversa casual | "Bom dia! Como posso ajudar?" |
| `info` | Azul (0,150,255) | Informação neutra | "A previsão do tempo é..." |
| `success` | Verde brilhante (50,255,50) | Ação bem-sucedida | "Pagamento realizado com sucesso!" |
| `warning` | Amarelo (255,200,0) | Atenção necessária | "A bateria está em 15%" |
| `alert` | Laranja (255,120,0) | Urgência moderada | "Porta da frente aberta há 10min" |
| `critical` | Vermelho (255,0,0) | Perigo/emergência | "Invasão detectada!" |
| `error` | Roxo (180,0,255) | Erro de sistema | "Falha ao conectar com servidor" |
| `security` | Vermelho piscante | Alerta segurança | "Movimento detectado no quintal" |

**Payload do evento:**
```json
{
  "event": "tts.speaking_started",
  "context": "critical",  // ← Brain define o contexto
  "message": "Invasão detectada na câmera frontal!"
}
```

### Estados do Sistema

| Evento NATS | Efeito LED | Descrição | Prioridade |
|-------------|------------|-----------|------------|
| `system.started` | Breathing azul lento | Sistema aguardando ativação | 1 |
| `wake_word.detected` | Flash branco 2x + Fade azul→verde (300ms) | Wake word detectado, atenção! | 5 |
| `speaker.verified` | Verde sólido (90% brilho) | Usuário autorizado, pode falar | 6 |
| `conversation.started` | Breathing verde médio | Conversação ativa | 7 |
| `brain.processing` | Spinner amarelo (3 LEDs girando) | LLM processando resposta | 8 |
| `tts.speaking_started` | **ATIVA CANAL 2** + Cor baseada em `context` | TTS começou a falar | 7 |
| `tts.speaking` (Canal 2 ativo) | Cor contextual pulsando (sync com volume) | LED sincronizado com voz | 7 |
| `tts.speaking_stopped` | **DESATIVA CANAL 2** | TTS parou de falar | 6 |
| `conversation.ended` | Fade para azul (500ms) + Breathing azul | Voltando ao idle | 6 |
| `error.*` | Roxo piscando 3x (200ms on/off) | Erro crítico | **10** |
| `security.intrusion` | Vermelho strobe contínuo | Alerta de segurança | **10** |
| `system.shutdown` | Fade para preto (1s) | Sistema desligando | 9 |

### Sistema de Prioridades

```python
# Prioridade mais alta sempre sobrescreve a mais baixa
PRIORITY_MAP = {
    "security.*": 10,        # Máxima
    "error.*": 10,           # Máxima
    "security.*": 10,
    "system.shutdown": 9,
    "brain.processing": 8,
    "conversation.started": 7,
    "tts.speaking": 7,
    "speaker.verified": 6,
    "conversation.ended": 6,
    "wake_word.detected": 5,
    "system.started": 1      # Mínima (idle)
}
```

---

## 🔊 ZeroMQ Audio Stream (Canal 2)

### Fluxo de Sincronização TTS ↔ LED

```
1. Evento NATS recebido: tts.speaking_started
   ↓
2. visual-feedback conecta no ZeroMQ do TTS Engine
   - Endpoint: tcp://tts-engine:5556
   - Topic: "audio.output"
   ↓
3. Recebe chunks de áudio via ZeroMQ:
   - Format: S16_LE (16-bit PCM)
   - Sample Rate: 16000 Hz
   - Chunk Size: 1024 samples (~64ms)
   ↓
4. Processa cada chunk recebido:
   - Calcula amplitude RMS:
     rms = sqrt(mean(audio_chunk ** 2))
   - Normaliza: amplitude = min(rms / threshold, 1.0)
   ↓
5. Mapeia amplitude → brilho LED:
   - amplitude 0.0–0.1 → brilho 50 (mínimo visível)
   - amplitude 0.1–0.5 → brilho 50-150 (linear)
   - amplitude 0.5–1.0 → brilho 150-255 (linear)
   ↓
6. Atualiza LED Ring:
   - Cor: baseada no contexto do Brain (normal=verde, critical=vermelho, etc)
   - Brilho: calculado acima (RMS)
   - Latência total: ~5-10ms
   ↓
7. Evento NATS recebido: tts.speaking_stopped
   ↓
8. Desconecta do ZeroMQ
   ↓
9. LED volta ao estado anterior (conversation.started)
```

### Código do Listener NATS (Define Cor Contextual)

```python
import asyncio
import nats
import json

# Variável global compartilhada com audio_stream_thread
current_color_rgb = (0, 255, 0)  # Padrão: verde
tts_active = False

CONTEXT_COLORS = {
    "normal": (0, 255, 0),
    "info": (0, 150, 255),
    "success": (50, 255, 50),
    "warning": (255, 200, 0),
    "alert": (255, 120, 0),
    "critical": (255, 0, 0),
    "error": (180, 0, 255),
    "security": (255, 0, 0)
}

async def nats_listener():
    nc = await nats.connect("nats://nats:4222")
    
    async def message_handler(msg):
        global current_color_rgb, tts_active
        
        event_name = msg.subject
        data = json.loads(msg.data.decode())
        
        if event_name == "tts.speaking_started":
            # Brain define o contexto da situação no payload
            context = data.get("context", "normal")
            current_color_rgb = CONTEXT_COLORS.get(context, (0, 255, 0))
            tts_active = True  # Ativa stream de áudio
            
            print(f"[LED] TTS ativo | Contexto: {context} | Cor: {current_color_rgb}")
        
        elif event_name == "tts.speaking_stopped":
            tts_active = False  # Desativa stream de áudio
    
    await nc.subscribe(">", cb=message_handler)
```

### Código de Stream (Pseudocódigo)

```python
import zmq
import numpy as np

# Cor contextual (definida pelo evento NATS tts.speaking_started)
current_color_rgb = (0, 255, 0)  # Padrão: verde (normal)

CONTEXT_COLORS = {
    "normal": (0, 255, 0),
    "info": (0, 150, 255),
    "success": (50, 255, 50),
    "warning": (255, 200, 0),
    "alert": (255, 120, 0),
    "critical": (255, 0, 0),
    "error": (180, 0, 255),
    "security": (255, 0, 0)
}

def audio_stream_thread():
    """Thread que escuta ZeroMQ quando TTS está ativo"""
    
    # Configuração ZeroMQ
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://tts-engine:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "audio.output")
    
    while tts_active:
        try:
            # Recebe chunk de áudio do TTS
            topic = socket.recv_string()
            audio_data = socket.recv()
            
            # Converte bytes → numpy array
            audio_chunk = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calcula amplitude (RMS)
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            amplitude = min(rms / 3000.0, 1.0)  # Threshold ajustável
            
            # Mapeia amplitude → brilho
            brightness = int(50 + (amplitude * 205))  # 50-255
            
            # Aplica cor contextual com brilho variável
            r, g, b = current_color_rgb
            r_adjusted = int((r / 255.0) * brightness)
            g_adjusted = int((g / 255.0) * brightness)
            b_adjusted = int((b / 255.0) * brightness)
            
            # Atualiza LED Ring
            for i in range(LED_COUNT):
                strip.setPixelColor(i, Color(r_adjusted, g_adjusted, b_adjusted))
            strip.show()
            
        except zmq.Again:
            time.sleep(0.01)  # Timeout, tenta de novo
    
    socket.close()
    context.term()
```

### Configuração ZeroMQ

```yaml
# config/zeromq.yml

connections:
  tts_audio_stream:
    endpoint: "tcp://tts-engine:5556"
    topic: "audio.output"
    socket_type: SUB
    timeout_ms: 100
    reconnect: true
    reconnect_interval_ms: 1000

processing:
  sample_rate: 16000
  chunk_size: 1024
  rms_threshold: 3000  # Ajustável conforme necessário
  
audio_reactive:
  enabled: true
  min_brightness: 50
  max_brightness: 255
  smoothing: 0.3  # Suavização (0-1)
```

---

## 🔧 Tecnologias

**Linguagem:** Python 3.11+

**Bibliotecas Core:**
- `rpi_ws281x`: Driver WS2812B para ARM64 (GPIO control)
- `nats-py`: Cliente NATS assíncrono
- `pyzmq`: Cliente ZeroMQ (stream de áudio)
- `numpy`: Processamento de sinais (RMS)
- `pyyaml`: Configuração dinâmica

**Dependências Sistema:**
- Nenhuma adicional (GPIO via kernel padrão)

---

## 📊 Especificações

```yaml
Hardware:
  LED Ring: WS2812B 12-16 LEDs
  GPIO Pin: 18 (PWM capable)
  Voltagem: 5V
  Corrente: ~60mA por LED @ 100% branco (720-960mA total)

Recursos Container:
  CPU: < 2% (idle), ~5% (stream ZeroMQ ativo)
  RAM: ~ 30 MB
  Latência: < 10 ms (evento → LED)
  Refresh Rate: ~60 Hz (baseado em chunks TTS), event-driven (NATS)

Privilégios:
  - Acesso GPIO (/dev/gpiomem)
  - Rede (para ZeroMQ e NATS)
```

---

## 🔌 Integração NATS

### Eventos Subscritos

```yaml
# Pattern matching para todos eventos relevantes
Subscriptions:
  - "wake_word.detected"
  - "speaker.verified"
  - "speaker.verification.failed"
  - "conversation.started"
  - "conversation.ended"
  - "brain.processing.started"
  - "brain.processing.completed"
  - "tts.speaking_started"
  - "tts.speaking_stopped"
  - "error.*"                    # Wildcard para todos erros
  - "security.*"                 # Wildcard para alertas de segurança
  - "system.started"
  - "system.shutdown"
  - "iot.device.unavailable"     # Opcional: feedback de IoT
```

### Eventos Publicados

```yaml
# Status periódico (Heartbeat)
Subject: "visual.feedback.status"
Payload:
  {
    "led_count": 12,
    "current_effect": "audio_reactive",
    "current_context": "normal",
    "current_color": [0, 255, 0],
    "brightness": 128,
    "audio_analysis_active": true,
    "uptime_seconds": 86400
  }
Interval: A cada 60 segundos
```

### Exemplos de Payloads do Brain

```json
// Situação 1: Conversa casual
{
  "event": "tts.speaking_started",
  "context": "normal",
  "message": "Bom dia! Como posso ajudar você hoje?"
}
// LED: Verde pulsando

// Situação 2: Alerta de segurança
{
  "event": "tts.speaking_started",
  "context": "critical",
  "message": "Invasão detectada na câmera frontal!"
}
// LED: Vermelho pulsando

// Situação 3: Aviso moderado
{
  "event": "tts.speaking_started",
  "context": "warning",
  "message": "A bateria do tablet está em 15%"
}
// LED: Amarelo pulsando

// Situação 4: Confirmação de ação
{
  "event": "tts.speaking_started",
  "context": "success",
  "message": "Pagamento de R$ 150 realizado com sucesso!"
}
// LED: Verde brilhante pulsando

// Situação 5: Informação neutra
{
  "event": "tts.speaking_started",
  "context": "info",
  "message": "A previsão do tempo para hoje é de 28 graus"
}
// LED: Azul pulsando
```

---

## ⚙️ Configuração Dinâmica

### Arquivo de Configuração

```yaml
# config/led-effects.yml

hardware:
  led_count: 12
  gpio_pin: 18
  brightness_max: 255
  brightness_min: 50

audio_sync:
  enabled: true
  zeromq_endpoint: "tcp://tts-engine:5556"
  zeromq_topic: "audio.output"
  sample_rate: 16000
  chunk_size: 1024
  amplitude_threshold: 3000  # RMS threshold para normalização

context_colors:
  # Mapeamento contexto → cor RGB (Brain define no evento)
  normal: [0, 255, 0]        # Verde
  info: [0, 150, 255]        # Azul
  success: [50, 255, 50]     # Verde brilhante
  warning: [255, 200, 0]     # Amarelo
  alert: [255, 120, 0]       # Laranja
  critical: [255, 0, 0]      # Vermelho
  error: [180, 0, 255]       # Roxo
  security: [255, 0, 0]      # Vermelho (+ efeito strobe)

effects:
  breathing:
    min_brightness: 20
    max_brightness: 255
    speed_slow: 2000    # ms para ciclo completo
    speed_medium: 1000
    speed_fast: 500
  
  spinner:
    led_count: 3        # Quantos LEDs acesos girando
    speed: 50           # ms por step
    trail_fade: true    # LEDs anteriores com fade
  
  flash:
    duration: 100       # ms por flash
    pause: 100          # ms entre flashes
  
  fade:
    duration: 300       # ms para transição completa

colors:
  blue: [0, 0, 255]
  green: [0, 255, 0]
  yellow: [255, 255, 0]
  red: [255, 0, 0]
  white: [255, 255, 255]
  orange: [255, 165, 0]

event_mapping:
  "system.started":
    effect: breathing
    color: blue
    speed: slow
    priority: 1
  
  "wake_word.detected":
    effect: flash_transition
    flash_color: white
    flash_count: 2
    from_color: blue
    to_color: green
    fade_duration: 300
    priority: 5
  
  "conversation.started":
    effect: breathing
    color: green
    speed: medium
    priority: 7
  
  "brain.processing.started":
    effect: spinner
    color: yellow
    priority: 8
  
  "tts.speaking_started":
    effect: audio_reactive
    # Cor é dinâmica: definida pelo campo "context" do evento
    # Exemplo: {"event": "tts.speaking_started", "context": "critical"}
    priority: 7
  
  "error.*":
    effect: blink
    color: red
    blink_count: 3
    speed: fast
    priority: 10
```

---

## 🐳 Docker Configuration

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY config/ ./config/

# Expor porta para métricas (opcional)
EXPOSE 8003

# Rodar com privilégios para GPIO
CMD ["python", "src/main.py"]
```

### requirements.txt

```txt
# NATS
nats-py==2.6.0

# LED Control
rpi-ws281x==5.0.0

# ZeroMQ Stream
pyzmq==25.1.2
numpy==1.26.0

# Config
pyyaml==6.0.1

# Utils
asyncio==3.4.3
```

### docker-compose.yml

```yaml
services:
  visual-feedback:
    container_name: visual-feedback
    build: ./visual-feedback
    restart: unless-stopped
    
    privileged: true  # Necessário para GPIO
    
    devices:
      - /dev/gpiomem:/dev/gpiomem  # GPIO access
    
    volumes:
      - ./config/led-effects.yml:/app/config/led-effects.yml:ro
      - /sys/class/gpio:/sys/class/gpio  # GPIO sysfs
    
    environment:
      - NATS_URL=nats://nats:4222
      - LED_COUNT=12
      - GPIO_PIN=18
      - LOG_LEVEL=INFO
    
    networks:
      - mordomo-net
    
    depends_on:
      - nats
      - tts-engine
    
    deploy:
      resources:
        limits:
          memory: 50M
          cpus: '0.1'
        reservations:
          memory: 20M
```

---

## 🎯 Fluxo Completo de Interação

```
USUÁRIO: "ASLAM"
  ↓
[wake-word-detector] detecta
  ↓ NATS: wake_word.detected
  ↓
[visual-feedback] escuta
  ↓
LED: Pisca branco 2x → Fade azul→verde (300ms)
════════════════════════════════════════════════════
  ↓
[speaker-verification] confirma voz
  ↓ NATS: speaker.verified
  ↓
[visual-feedback] escuta
  ↓
LED: Verde sólido brilhante (90%)
════════════════════════════════════════════════════
  ↓
USUÁRIO: "Qual o clima hoje?"
  ↓
[whisper-asr] transcreve
  ↓
[orchestrator] inicia conversa
  ↓ NATS: conversation.started
  ↓
[visual-feedback] escuta
  ↓
LED: Verde breathing médio
════════════════════════════════════════════════════
  ↓
[brain] processa intenção
  ↓ NATS: brain.processing.started
  ↓
[visual-feedback] escuta
  ↓
LED: Amarelo spinner (3 LEDs girando)
════════════════════════════════════════════════════
  ↓
[brain] retorna resposta
  ↓
[tts-engine] gera áudio
  ↓ NATS: tts.speaking_started
  ↓
[visual-feedback] escuta
  ↓
LED: Ativa Canal 2 (análise de áudio)
  ↓
LED: Verde pulsando no ritmo da fala
  |  (volume → brilho em tempo real)
  |  Latência: ~5ms
  ↓
[tts-engine] termina de falar
  ↓ NATS: tts.speaking_stopped
  ↓
[visual-feedback] escuta
  ↓
LED: Desativa Canal 2
════════════════════════════════════════════════════
  ↓
[orchestrator] encerra conversa
  ↓ NATS: conversation.ended
  ↓
[visual-feedback] escuta
  ↓
LED: Fade verde→azul (500ms) → Breathing azul lento
```

---

## 🧪 Testes e Debugging

### Teste Manual via NATS CLI

```bash
# Publicar evento de teste
nats pub wake_word.detected '{"timestamp": "2026-02-19T10:30:00Z"}'

# Observar resposta
# LED deve piscar branco 2x + fade azul→verde

# Testar prioridades
nats pub error.critical '{"message": "Out of memory"}'
# LED deve imediatamente virar vermelho piscando (sobrescreve qualquer estado)
```

### Logs Esperados

```
[INFO] visual-feedback started (LED count: 12, GPIO: 18)
[INFO] Connected to NATS: nats://nats:4222
[INFO] Subscribed to 13 event patterns
[INFO] Current state: IDLE (breathing_blue)
[DEBUG] Event received: wake_word.detected (priority: 5)
[DEBUG] Transitioning: IDLE → WAKE_DETECTED
[INFO] Effect: flash_white_2x + fade(blue→green, 300ms)
[DEBUG] Event received: speaker.verified (priority: 6)
[INFO] Effect: solid_green(90%)
[DEBUG] Event received: tts.speaking_started (priority: 7)
[INFO] Audio analysis ENABLED (Canal 2)
[DEBUG] RMS: 2850, Volume: 0.85, Brightness: 224
[DEBUG] Event received: tts.speaking_stopped (priority: 7)
[INFO] Audio analysis DISABLED (Canal 2)
```

---

## 📈 Roadmap Futuro

### Fase 1 (MVP) ✅
- Sistema híbrido NATS + análise local
- 10 eventos principais mapeados
- LED Ring 12 LEDs
- Configuração estática (YAML)

### Fase 2 (Melhorias)
- Dashboard web para testar efeitos ao vivo
- Suporte a múltiplos rings (multi-room)
- Configuração dinâmica via NATS
- Efeitos customizados por usuário

### Fase 3 (Avançado)
- Machine learning para efeitos adaptativos
- Sincronização com música (Entretenimento module)
- API REST para integração com apps externos
- Suporte a LED strips (não apenas rings)

---

## 🔗 Dependências

### Módulos Requeridos
- **NATS** (infraestrutura): Message broker
- **TTS Engine**: Para sincronização de áudio
- **Orchestrator**: Para eventos de conversação

### Módulos Opcionais
- **IoT**: Para feedback de dispositivos
- **Security**: Para alertas visuais
- **Dashboard UI**: Para configuração visual

---

## 📚 Referências Técnicas

- [WS2812B Datasheet](https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf)
- [rpi_ws281x Library](https://github.com/jgarff/rpi_ws281x)
- [ZeroMQ Guide](https://zeromq.org/documentation/)
- [PyZMQ Documentation](https://pyzmq.readthedocs.io/)
- [NATS Python Client](https://github.com/nats-io/nats.py)
- [Audio RMS Calculation](https://en.wikipedia.org/wiki/Root_mean_square)

---

**Status:** 📋 Especificado (Aguardando implementação)  
**Repositório:** [AslamSys/mordomo-visual-feedback](https://github.com/AslamSys/mordomo-visual-feedback)  
**Última atualização:** 2026-02-19

