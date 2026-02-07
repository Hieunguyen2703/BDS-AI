# 📋 Phân Chia Công Việc - Dự Án BDS Agent (NHÓM 5 - VSMAC)

Tài liệu này phân chia trách nhiệm cho 5 thành viên (3 Backend - 2 Frontend) để tối ưu hóa việc phát triển hệ thống.

---

### 🱔 NHÓM BACKEND (3 Thành viên)

#### 👤 Thành viên 1: Trưởng nhóm & Kỹ sư Scraper (Backend 1)
**Trọng tâm:** Thu thập dữ liệu và hạ tầng crawler.
*   **Nhiệm vụ:**
    *   Phát triển và bảo trì các bộ cào dữ liệu (`agents/`).
    *   Xử lý các cơ chế vượt chặn (Proxy, Captcha) và tối ưu hóa tốc độ cào.
    *   Quản lý Docker Compose và hạ tầng server (PostgreSQL, Redis, ChromaDB).
    *   Quản lý tiến độ chung và điều phối các thành viên.

#### 👤 Thành viên 2: Kỹ sư Học máy & Định giá (Backend 2)
**Trọng tâm:** Mô hình dự báo giá và phân tích dữ liệu.
*   **Nhiệm vụ:**
    *   Huấn luyện và tối ưu mô hình **AutoGluon** (`services/ml_service.py`).
    *   Xây dựng thuật toán phân tích xu hướng giá thị trường.
    *   Đảm bảo tính chính xác và logic của service định giá bất động sản.
    *   Phát triển các API tính toán thống kê phức tạp.

#### 👤 Thành viên 3: Kỹ sư AI & Search Engine (Backend 3)
**Trọng tâm:** Trí tuệ nhân tạo và Tìm kiếm ngữ nghĩa.
*   **Nhiệm vụ:**
    *   Tích hợp và quản lý LLM (Gemini & Fallback Ollama).
    *   Xây dựng hệ thống RAG với **ChromaDB** để tìm kiếm theo ý nghĩa.
    *   Thiết kế Prompt Engineering cho chatbot tư vấn.
    *   Xây dựng logic API v1 cho hệ thống tìm kiếm thông minh.

---

### 🎨 NHÓM FRONTEND (2 Thành viên)

#### 👤 Thành viên 4: Kỹ sư UI/UX & Interaction (Frontend 1)
**Trọng tâm:** Giao diện người dùng và Trải nghiệm thị giác.
*   **Nhiệm vụ:**
    *   Xây dựng Layout chính, Header, Footer và hệ thống Design System.
    *   Thiết kế hiệu ứng thẩm mỹ Space AI (Background glow, animations).
    *   Đảm bảo trải nghiệm Responsive mượt mà trên mọi thiết bị.
    *   Quản lý trạng thái ứng dụng (Zustand) và logic điều hướng.

#### 👤 Thành viên 5: Kỹ sư Data Visualization & Features (Frontend 2)
**Trọng tâm:** Chỉnh sửa các tính năng và trực quan hóa dữ liệu.
*   **Nhiệm vụ:**
    *   Phát triển các trang chức năng: Tìm kiếm, Định giá, Phân tích.
    *   Tích hợp các biểu đồ Recharts để hiển thị xu hướng thị trường.
    *   Xử lý tích hợp API từ Backend vào giao diện người dùng.
    *   Xây dựng Chat Widget và các component tương tác dữ liệu.

---

### 📅 Quy trình phối hợp
1.  **Backend-First**: Backend bàn giao Swagger/API docs sớm nhất để Frontend tích hợp.
2.  **Git flow**: Mỗi thành viên làm việc trên branch riêng, Review trước khi merge vào `main`.
3.  **Họp nhanh**: 15 phút đầu giờ để đồng bộ các đầu việc.

**Phát triển bởi**: NHÓM 5 - VSMAC
