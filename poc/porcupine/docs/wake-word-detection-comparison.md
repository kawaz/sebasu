# Wake Word Detection Libraries Comparison

## Executive Summary

This document provides a comprehensive comparison of three wake word detection libraries: **Porcupine (by Picovoice)**, **Picovoice Wake Word**, and **OpenWakeWord**. Each library offers different approaches to wake word detection with varying trade-offs between performance, licensing, and ease of use.

## Comparison Table

| Feature | Porcupine | OpenWakeWord |
|---------|-----------|--------------|
| **Developer** | Picovoice | David Scripka (Open Source) |
| **License** | Commercial with Free Tier | Apache 2.0 (Open Source) |
| **Accuracy** | 97%+ detection rate, <1 false alarm/10hrs | Variable, configurable sensitivity |
| **Latency** | Real-time, sub-100ms | 80ms frame processing |
| **Platform Support** | Linux, Mac, Windows, iOS, Android, Raspberry Pi, embedded | Linux, Windows, Raspberry Pi (limited embedded) |
| **Language Support** | 17+ languages publicly available (40 total) | Primarily English |
| **Resource Requirements** | Low (200KB tiny model available) | Moderate (too large for microcontrollers) |
| **CPU Usage** | Minimal, scales without overhead | 15-20 models on single RPi3 core |
| **Custom Wake Words** | Yes, instant training via console | Yes, requires ~1 hour training |
| **Pre-trained Models** | Alexa, Siri, Google, custom | Various including Alexa |
| **Integration Complexity** | Easy SDK, multiple language bindings | Python-based, ONNX/TFLite runtime |
| **Pricing** | Free tier (3 users), Commercial plans | Completely free |

## 1. Technical Specifications

### Porcupine (Picovoice)
- **Accuracy**: 97%+ detection rate with less than 1 false alarm per 10 hours
- **Latency**: Real-time processing with sub-100ms response time
- **Audio Format**: 16-bit PCM, single-channel, 16kHz
- **Model Sizes**: Standard and tiny (200KB) models available
- **Architecture**: Deep neural networks trained on real-world data
- **Performance**: 2.53x more accurate, 2.6x faster than competitors on Raspberry Pi 3

### OpenWakeWord
- **Accuracy**: Configurable false-accept/false-reject rates
- **Latency**: 80ms frame processing, may take seconds on ESP32-S3
- **Audio Format**: 80ms frames with melspectrogram processing
- **Architecture**: TTS-based synthetic training data, shared feature extraction backbone
- **Performance**: Can run 15-20 models simultaneously on Raspberry Pi 3

## 2. Licensing and Pricing Models

### Porcupine (Picovoice)
- **Free Tier**: 
  - Personal non-commercial projects
  - Commercial use up to 3 users
  - No credit card required
  - 3 wake word training limit per month
- **Foundation Plan**: Commercial usage with click-through payment
- **Enterprise Plan**: Custom terms and support
- **Notable**: Free licensing for Alexa, Siri, and Google Assistant wake words

### OpenWakeWord
- **License**: Apache 2.0 (fully open source)
- **Cost**: Completely free for all uses
- **No restrictions** on commercial use or user limits

## 3. Language and Wake Word Support

### Porcupine
- **Languages**: 17 publicly available (English, French, German, Italian, Japanese, Korean, Chinese, Portuguese, Spanish, etc.)
- **Total**: Up to 40 languages with enterprise support
- **Multilingual**: Can run multiple languages simultaneously with no performance penalty
- **Custom Wake Words**: Instant training through web console, no data collection required

### OpenWakeWord
- **Languages**: Primarily English (based on available documentation)
- **Custom Wake Words**: Requires training with synthetic TTS data (~1 hour process)
- **Pre-trained Models**: Several available including "Alexa"

## 4. Resource Requirements

### Porcupine
- **CPU**: Minimal overhead, efficient scaling
- **Memory**: 45% less than competitors
- **Embedded**: Tiny model (200KB) for deeply embedded systems
- **Power**: Optimized for battery-powered devices

### OpenWakeWord
- **CPU**: Moderate requirements
- **Memory**: Too large for microcontrollers
- **Best suited**: Raspberry Pi level devices and above
- **Not recommended**: ESP32 or similar constrained devices

## 5. Integration Complexity

### Porcupine
- **SDKs**: Available for multiple languages (Python, JavaScript, Java, Swift, etc.)
- **APIs**: High-level (PorcupineManager) and low-level APIs
- **Documentation**: Comprehensive with tutorials
- **Setup**: Simple initialization with access key

### OpenWakeWord
- **Language**: Python-based
- **Dependencies**: ONNX Runtime or TFLite
- **Integration**: Direct audio stream processing
- **Custom Models**: Colab notebook provided for training

## 6. Pros and Cons

### Porcupine

**Pros:**
- Superior accuracy and performance
- Extensive language support
- Minimal resource requirements
- Professional support available
- Instant custom wake word training
- Works on embedded devices

**Cons:**
- Proprietary/commercial
- Limited free tier for commercial use
- Requires API key management

### OpenWakeWord

**Pros:**
- Completely free and open source
- No licensing restrictions
- Transparent architecture
- Community-driven development
- Good for prototyping

**Cons:**
- Limited language support
- Higher resource requirements
- Not suitable for embedded devices
- Requires more effort for custom wake words
- Lower accuracy in noisy environments

## 7. Use Cases and Recommendations

### Choose Porcupine when:
- Building commercial products
- Requiring multilingual support
- Deploying on embedded/IoT devices
- Needing highest accuracy and lowest latency
- Want professional support
- Building battery-powered devices

### Choose OpenWakeWord when:
- Building open-source projects
- Running on Raspberry Pi or desktop
- Budget is extremely constrained
- Want full control over the codebase
- Prototyping or educational purposes
- English-only applications

## Conclusion

**Porcupine** emerges as the clear leader for production-grade, commercial applications requiring high accuracy, low latency, and embedded device support. Its extensive language support and minimal resource requirements make it ideal for professional products.

**OpenWakeWord** serves as an excellent open-source alternative for hobbyists, researchers, and developers building English-language applications on more powerful hardware. While it may not match Porcupine's performance on embedded devices, its zero-cost and open nature make it valuable for many use cases.

The choice between these libraries ultimately depends on your specific requirements regarding performance, budget, hardware constraints, and language support needs.