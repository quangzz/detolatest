# Feature: Hệ thống AI KOC Discovery tối ưu Token, An toàn & Tự phục hồi

```gherkin
Feature: Phễu lọc 5 tầng tìm kiếm KOC TikTok quảng bá Kem chống nắng

  Scenario: Lọc cứng 0-token loại bỏ hồ sơ vượt ngân sách và thuần Livestream ở Stage 1
    Given ngân sách chiến dịch là 30000000 VNĐ cho 5 KOC mục tiêu
    And tập ứng viên có chứa Mega KOL 920000 followers và kênh Livestream chiếm 97% doanh thu
    When hệ thống thực thi Stage 0 và Stage 1
    Then các hồ sơ Mega KOL và kênh thuần Livestream bị loại với đúng 0 LLM token tiêu tốn
    And chỉ các Nano/Micro-KOC phù hợp khung ngân sách mới đi tiếp sang Stage 2

  Scenario: Khôi phục tiến độ từ SQLite WAL Checkpoint không tốn lại token cũ
    Given một phiên chạy bị ngắt giữa chừng sau khi hoàn tất 2 KOC đầu tiên ở Stage 3
    When người vận hành chạy lệnh resume trên cùng job_id
    Then trạng thái Stage 0, Stage 1, Stage 2 và 2 KOC đầu của Stage 3 được khôi phục từ checkpoints.db
    And không có lời gọi LLM trùng lặp nào được phát sinh cho 2 KOC đã hoàn tất

  Scenario: Tổng ngân sách danh mục đề xuất luôn tuân thủ trần 30 triệu VNĐ
    Given danh sách Finalists đã có báo cáo phân tích Contact Sheet 3x3 ở Stage 3
    When Stage 4 tổng hợp danh mục 5 KOC tối ưu
    Then tổng allocated_budget_vnd cộng reserve_seeding_budget_vnd bằng đúng hoặc nhỏ hơn 30000000 VNĐ
    And mỗi KOC đều đính kèm bằng chứng hiệu suất và bằng chứng khung hình video

  Scenario: Phòng chống SSRF, Path Traversal và Reverse Tabnabbing
    Given đầu vào chứa URL nội bộ "http://127.0.0.1:8080/secret" hoặc mã định danh "../outside"
    When qua lớp kiểm định src/core/security.py và xuất báo cáo HTML
    Then URL nội bộ bị từ chối bởi bộ lọc SSRF và mã định danh bị chặn Path Traversal
    And mọi liên kết mở tab mới trong report.html đều có thuộc tính rel="noopener noreferrer"
```
