# 🚌 Carris Metropolitana — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Integração para Home Assistant que monitoriza as linhas, paragens e veículos da Carris Metropolitana (Área Metropolitana de Lisboa).

## ✨ Funcionalidades
- 🗺️ Filtragem por município
- 🚌 Escolha de linhas a monitorizar
- 🕐 Próximas chegadas por paragem em tempo real
- 📍 Contagem e posição de veículos por linha
- 🚨 Alertas de serviço ativos
- ♻️ Atualização automática a cada minuto
- 🔧 Configuração pela UI — sem YAML

## 📦 Instalação via HACS

1. Clica no botão "Adicionar ao HACS" acima
2. Confirma a instalação no teu Home Assistant
3. Reinicia o Home Assistant
4. Vai a Definições → Dispositivos e Serviços → + Adicionar integração
5. Procura **Carris Metropolitana** e segue o assistente

### Instalação manual via HACS
1. Abre o HACS no Home Assistant
2. Clica em **Integrações** → menu ⋮ → **Repositórios personalizados**
3. Adiciona: `https://github.com/leothemurphy41/ha-carrismetropolitana` Categoria: **Integração**
4. Procura **Carris Metropolitana** e instala

## ⚙️ Configuração

O assistente tem 3 passos:

| Passo | Descrição |
|-------|-----------|
| 1. Municípios | Selecione os municípios da AML |
| 2. Linhas | Escolha as linhas de autocarro |
| 3. Paragens | Selecione paragens para chegadas em tempo real |

## 📡 Sensores criados

| Sensor | Descrição |
|--------|-----------|
| `sensor.carris_paragem_<ID>` | Próximas chegadas em tempo real |
| `sensor.carris_linha_<ID>` | Veículos ativos na linha + posição GPS |
| `sensor.carris_alertas` | Alertas de serviço ativos |

## 🔗 Fonte de dados

API pública da [Carris Metropolitana](https://www.carrismetropolitana.pt)