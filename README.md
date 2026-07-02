# 🔱 ZERO CUTLOSS EMPIRE — Autonomous Trading Agent Swarm
## 🔱 ZERO CUTLOSS EMPIRE — Hệ Thống Bầy Đàn Agent Giao Dịch Tự Chủ

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Supported-orange.svg)](https://docs.docker.com/compose/)

---

### 🌐 INTRODUCTION / GIỚI THIỆU

#### [English]
**Zero Cutloss Empire** is a state-of-the-art, cloud-native autonomous multi-agent system designed for quantitative trading and market intelligence. Powered by a collaborative swarm of 12 specialized AI agents, the system continuous monitors, analyzes, and executes trading strategies without utilizing traditional cutloss limits, relying instead on sophisticated hedging, Wyckoff phase analysis, and market manipulation detection. 

The architecture leverages various advanced LLM providers (Gemini, Groq, OpenRouter, Cerebras) to distribute cognitive workloads, ensuring low latency, high resilience, and complex logical reasoning.

#### [Tiếng Việt]
**Zero Cutloss Empire** là hệ thống đa agent tự chủ tiên tiến, vận hành trên nền tảng đám mây được thiết kế cho giao dịch định lượng và phân tích thị trường. Được vận hành bởi một bầy đàn gồm 12 AI Agent chuyên biệt cộng tác song song, hệ thống liên tục giám sát, phân tích và thực thi chiến lược giao dịch mà không cần sử dụng các giới hạn cắt lỗ truyền thống (cutloss), thay vào đó dựa trên các cơ chế phòng vệ (hedging) phức tạp, phân tích pha Wyckoff và phát hiện thao túng thị trường.

Kiến trúc hệ thống tận dụng linh hoạt các nhà cung cấp Cloud LLM (Gemini, Groq, OpenRouter, Cerebras) để phân bổ tải nhận thức, đảm bảo độ trễ thấp, tính phục hồi cao và khả năng lập luận logic chuyên sâu.

---

### 🔱 SWARM ARCHITECTURE / KIẾN TRÚC BẦY ĐÀN (12 AGENTS)

| Agent ID | Name (EN / VI) | Core Role & Responsibility / Vai Trò & Nhiệm Vụ Cốt Lõi |
| :---: | :--- | :--- |
| **A01** | **Orderbook Hound** <br> *(Huyết Trảo)* | Tracks real-time orderbooks, spreads, spoofing walls, volume, and Open Interest (OI) from Binance/Bybit. <br> *Theo dõi sổ lệnh, spread, tường lệnh giả (spoofing), volume và Open Interest (OI) thời gian thực.* |
| **A02** | **Macro Phantom** <br> *(Bóng Ma Vĩ Mô)* | Monitors global macro climates, Fear & Greed index, and overall market regimes. <br> *Giám sát thời tiết vĩ mô toàn cầu, chỉ số Sợ hãi & Tham lam, và xu hướng vĩ mô.* |
| **A03** | **Social Crawler** <br> *(Cào Tin Tức)* | Scrapes Telegram, Reddit, Twitter, and financial news for sentiment, hype, and FUD detection. <br> *Quét dữ liệu Telegram, Reddit, Twitter và tin tức để phân tích tâm lý thị trường.* |
| **A04** | **Wyckoff & Elliott Scholar** <br> *(Ngũ Đại Học Giả)* | Analyzes multi-timeframe charts using Wyckoff phase analysis, Elliott Wave, and high-frequency metrics. <br> *Phân tích kỹ thuật đa khung thời gian theo pha Wyckoff, Sóng Elliott và các chỉ báo cao tần.* |
| **A05** | **Decision Judge** <br> *(Trọng Tài Phán Quyết)* | Evaluates risk, calculates capital allocation, and makes the final trading decisions. <br> *Thẩm định rủi ro, tính toán phân bổ vốn và đưa ra phán quyết giao dịch cuối cùng.* |
| **A06** | **Syndicate Butler** <br> *(Quản Gia Swarm)* | Acts as the interface via Telegram, broadcasting alerts, sending reports, and executing user commands. <br> *Đóng vai trò giao diện điều hành qua Telegram, phát cảnh báo, báo cáo và nhận lệnh.* |
| **A07** | **Execution Queen** <br> *(Nữ Vương Hành Quyết)* | Manages orders, executes trades, and handles portfolio rebalancing on exchanges. <br> *Quản lý lệnh, thực thi giao dịch và cân bằng danh mục tài sản trên các sàn.* |
| **A08** | **Swarm Engine** <br> *(Cá Thể Tài Chính)* | Simulates millions of retail trader behaviors to forecast short-term price directions. <br> *Mô phỏng hành vi của đám đông nhỏ lẻ để dự báo hướng đi của giá trong ngắn hạn.* |
| **A09** | **Immunity Sentinel** <br> *(Hệ Miễn Dịch)* | Monitors swarm health, checks agent heartbeats, and acts as a circuit breaker during anomalies. <br> *Giám sát sức khỏe bầy đàn, nhịp tim các agent và kích hoạt ngắt mạch khi có sự cố.* |
| **A10** | **Shadow Collector** <br> *(Bóng Tối)* | Tracks whale wallet transactions, smart contracts, and on-chain liquidity flows. <br> *Theo dõi dòng tiền của ví cá voi, tương tác hợp đồng thông minh và thanh khoản on-chain.* |
| **A11** | **Flow Strategist** <br> *(Chiến Lược Dòng Tiền)* | Analyzes volume profiling, net transaction flows, and market maker footprints. <br> *Phân tích mật độ volume, dòng giao dịch ròng và dấu chân của các nhà tạo lập thị trường.* |
| **A12** | **AEO Detective** <br> *(Thám Tử AEO)* | Detects Artificial Engagement Optimization and fake narratives created to trap retail traders. <br> *Phát hiện các hoạt động tạo cung cầu giả (AEO) và tin tức lùa gà nhằm bẫy retail traders.* |

---

### ⚡ CURRENT STATUS / TRẠNG THÁI HIỆN TẠI

#### [English]
- **Cloud-Only Operation**: The system is fully configured to execute on cloud LLM APIs, removing local GPU/Ollama dependencies for easy scaling and deployment on lightweight servers.
- **Robust Fallback Routing**: Integrated with `llm_router.py` to seamlessly route prompts across Gemini, Groq, OpenRouter, and Cerebras APIs when rate limits (429) occur.
- **Docker-Ready**: Packaged with a modular `docker-compose.yml` to orchestrate Redis, ChromaDB, Redlib, API Gateway, and the agent services with a single command.
- **State Persistence**: Uses Redis for real-time inter-agent messaging (Pub/Sub, streams) and ChromaDB for vector memory.

#### [Tiếng Việt]
- **Vận Hành Thuần Cloud**: Hệ thống được cấu hình đầy đủ để chạy trực tiếp qua API LLM đám mây, loại bỏ phụ thuộc vào GPU/Ollama local giúp dễ dàng triển khai trên các máy chủ cấu hình nhẹ.
- **Định Tuyến Phục Hồi Cao**: Tích hợp `llm_router.py` để tự động chuyển đổi luồng prompt giữa Gemini, Groq, OpenRouter và Cerebras khi gặp lỗi giới hạn tần suất (429).
- **Hỗ Trợ Docker**: Đóng gói sẵn với `docker-compose.yml` giúp khởi động Redis, ChromaDB, Redlib, API Gateway và toàn bộ bầy đàn chỉ với một câu lệnh duy nhất.
- **Bảo Toàn Trạng Thái**: Sử dụng Redis làm kênh truyền tin giữa các agent (Pub/Sub, streams) và ChromaDB để lưu trữ trí nhớ vector.

---

### 🔮 FUTURE VISION / TẦM NHÌN TƯƠNG LAI

#### [English]
- **Long-Term Strategic Positioning**: The system is designed not for short-term speculation, but for long-term strategic positioning and secure asset allocation. It operates with the perspective of fully informed entities that recognize market manipulation.
- **Multiverse Asset Expansion**: All trading decisions, market observations, and future expansions—such as integrating US equities, global stocks, foreign exchange (Forex), or other cryptocurrency exchanges—require the user to supply relevant APIs and parameters to give the swarm a comprehensive understanding of the market.
- **Unified Market Sensory Channel**: While even skilled traders often fail due to quantitative manipulation of indicators and news, this system acts as a unified sensory channel to identify underlying market structures. Long-term trends dominate short-term noise.
- **Leveraged Sub-Swarm Integration**: Users can leverage this core context to deploy short-term trading agents with appropriate leverage, capturing cash flow waves and avoiding potential market collapses.
- **Peer-to-Peer AI Investment Platform**: The ultimate vision is to build a peer-to-peer, reliable information-sharing and co-investment community. Zero Cutloss serves as the cornerstone for a future decentralized ecosystem where members share insights and co-invest, mutually sharing profits in digital currencies under the guidance and optimization of swarm AI intelligence.

#### [Tiếng Việt]
- **Định Vị Chiến Lược Dài Hạn**: Hệ thống không được thiết kế cho việc đầu cơ ngắn hạn, mà hướng đến một tầm nhìn dài hạn và các điểm dịch chuyển tài sản an toàn như những thực thể nắm giữ đầy đủ thông tin và hiểu biết về thao túng thị trường.
- **Mở Rộng Đa Tài Sản**: Mọi quyết định giao dịch, quan sát thị trường và mở rộng tính năng (chứng khoán Mỹ, chứng khoán toàn cầu, ngoại tệ, hoặc các sàn giao dịch khác) đều yêu cầu người dùng bổ sung API và tham số tương ứng để cung cấp đầy đủ ngữ cảnh giúp bầy đàn (swarm) thấu hiểu cấu trúc thị trường.
- **Kênh Nhận Diện Cấu Trúc Độc Lập**: Mỗi trader dù giỏi đến đâu vẫn thường bị dẫn dắt định lượng bởi các chỉ báo kỹ thuật hoặc tin tức nhiễu loạn. Hệ thống này đóng vai trò là một kênh tổng hợp độc lập nhằm nhận diện bản chất tình huống—nơi dài hạn chi phối ngắn hạn.
- **Tích Hợp Swarm Ngắn Hạn Có Đòn Bẩy**: Người dùng có thể tích hợp thêm các agent giao dịch ngắn hạn sử dụng đòn bẩy hợp lý trên nền tảng ngữ cảnh này để tận dụng các cơn sóng dòng tiền và chủ động rút lui trước các đợt sụp đổ tiềm tàng.
- **Nền Tảng Hợp Tác Đầu Tư & Chia Sẻ Thông Tin Ngang Hàng**: Tầm nhìn tối hậu là kiến tạo một cộng đồng chia sẻ thông tin ngang hàng (P2P) đáng tin cậy. Zero Cutloss là viên gạch nền móng cho một hệ sinh thái chia sẻ thông tin và đầu tư đồng hành lợi nhuận bằng tiền kỹ thuật số ảo kết hợp với nền tảng trí tuệ nhân tạo (AI) trong tương lai.

---

### 🔑 REQUIRED API KEYS / DANH SÁCH API CẦN THIẾT

#### [English]
To deploy the system, copy `config/.env.example` to `config/.env` and supply variables with empty values after the `=` sign:
- **Exchange Keys**: Binance/Bybit API keys with trading permissions disabled for safety during setup.
- **LLM Provider Keys**: Gemini API Key, Groq API Key, OpenRouter API Key, and Cerebras API Key.
- **Social Scraper Config**: Telegram API ID/Hash, Twitter API Keys, or Reddit credentials.

#### [Tiếng Việt]
Để triển khai hệ thống, sao chép file `config/.env.example` thành `config/.env` và nhập các biến với giá trị trống sau dấu `=`:
- **API Sàn**: API key của Binance/Bybit (khuyến nghị tắt quyền giao dịch khi mới thiết lập để đảm bảo an toàn).
- **API Nhà Cung Cấp LLM**: Gemini API Key, Groq API Key, OpenRouter API Key, và Cerebras API Key.
- **Cấu hình Cào Tin**: API ID/Hash của Telegram, API Key Twitter, hoặc tài khoản Reddit.

---

### 🚀 QUICK START / HƯỚNG DẪN NHANH

```bash
# 1. Clone the repository / Sao chép kho lưu trữ
git clone <repository_url>
cd Zero_Cutloss_Public

# 2. Configure environment variables / Cấu hình biến môi trường
cp config/.env.example config/.env
# Edit config/.env and fill in your API keys / Chỉnh sửa config/.env và nhập API keys

# 3. Start the Swarm / Khởi động Bầy Đàn
docker compose up -d --build
```
