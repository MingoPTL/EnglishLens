# EnglishLens — camera DroidCam + AI

## Cài trên máy khác để test (Windows)

Cần Git và Python 3.10. Trong PowerShell, chạy:

```powershell
git clone https://github.com/MingoPTL/EnglishLens.git
cd EnglishLens
py -3.10 -m venv .venv-ram
.\.venv-ram\Scripts\python.exe -m pip install torch==2.5.1 torchvision==0.20.1
.\.venv-ram\Scripts\python.exe -m pip install -r requirements.txt requests
git clone https://github.com/xinyu1205/recognize-anything.git vendor/recognize-anything
git -C vendor/recognize-anything checkout 7cb804a8609e9f4b1a50b7f31436d2df40bb9481
.\.venv-ram\Scripts\python.exe download_models.py
.\run.bat
```

Model tải khoảng 6,4 GB, cần Internet cho lần tải đầu. Git không chứa `models/`, `vendor/`, môi trường Python hoặc `outputs/`; các lệnh trên tạo lại những thành phần cần thiết. Có thể chạy bộ test trước khi tải model:

```powershell
.\.venv-ram\Scripts\python.exe -m unittest discover -s tests -v
```

Máy đã clone repo thì cập nhật bằng `git pull origin main`. Cấu hình môi trường `diemdanh` bên dưới là cấu hình riêng của máy phát triển; máy mới dùng môi trường độc lập tạo ở trên.

## Mở giao diện

Nhấp đúp **start-ui.cmd**. App tự chạy nền và mở trình duyệt. Đóng cửa sổ mở app không tắt máy chủ. Địa chỉ cố định trên máy này, dùng được khi đổi mạng hoặc không có Internet:
http://127.0.0.1:7860

1. Mở app DroidCam trên điện thoại, để điện thoại và PC cùng Wi-Fi.
2. Chọn **DroidCam Wi-Fi**, nhập IP và cổng hiện trong app. Mặc định cổng là 4747.
3. Bấm **Kết nối camera**. Mỗi lần mở giao diện nhập lại địa chỉ hiện tại, không tự kết nối địa chỉ cũ.
4. Khi Grounding DINO báo **Sẵn sàng**, nhập nhãn tiếng Anh (person, phone, bottle...) rồi bấm **Chụp & nhận diện** để xử lý một ảnh. Có thể bật nhận diện liên tục khi cần.
5. Khi RAM cũng sẵn sàng, có thể chọn **Tự tìm nhãn**.

Không cần DroidCam Client Windows khi kết nối IP. Giao diện cũng có tab Webcam nếu sau này dùng webcam/Client.
DroidCam phải cung cấp luồng MJPEG tại http://IP:PORT/video. Nếu phiên bản app không hỗ trợ luồng này, dùng DroidCam Client và tab Webcam.
Tài liệu: https://www.dev47apps.com/droidcam/connect/

## Cách hiển thị

- **Chụp & nhận diện** chỉ gửi một khung hình cho AI; kết quả giữ nguyên đến lần chụp kế tiếp. Nút bị khóa trong lúc xử lý để tránh gửi trùng.

- Khung trái là camera trực tiếp; khung phải là ảnh mới nhất AI đã phân tích, kèm bounding box.
- DroidCam truyền MJPEG liên tục tới trình duyệt, không chờ 80 ms giữa từng ảnh. Máy chủ giữ khung hình mới nhất và bỏ qua ảnh cũ khi bên xem chậm. Chỉ số FPS dưới camera là tốc độ nhận hình từ nguồn, không phải FPS nhận diện AI hoặc FPS màn hình.
- Webcam yêu cầu 30 FPS nếu thiết bị hỗ trợ. FPS thực tế của DroidCam phụ thuộc điện thoại, cấu hình DroidCam và Wi-Fi.
- AI xử lý một ảnh tại một thời điểm, lấy ảnh mới nhất sau khi xong; không xếp hàng gây trễ.
- Thời gian thực tế mỗi ảnh và giờ nhận kết quả hiển thị dưới khung AI. Không cam kết AI chạy 30 FPS.
- Nút Lưu ảnh lưu ảnh AI có bounding box xuống máy. Thử ảnh mẫu dùng ảnh trong repo RAM.
- Camera được xử lý local trên PC; máy chủ chỉ lắng nghe 127.0.0.1.
- Ngắt kết nối dừng luồng hình; nếu AI đang xử lý một ảnh thì lượt đó hoàn tất nhưng kết quả bị bỏ.
- Camera không phụ thuộc model. Nút AI chỉ bật khi các file model cần thiết đã tải xong.

## Model và môi trường

.venv-ram dùng Python 3.10 và --system-site-packages từ
E:\IDE\Miniconda3\envs\diemdanh để dùng lại torch 2.5.1+cu121 / torchvision 0.20.1+cu121.
Các thư viện bổ sung nằm trong .venv-ram; không sửa môi trường diemdanh.
Giữ môi trường diemdanh vì EnglishLens phụ thuộc vào nó; nâng cấp môi trường đó có thể ảnh hưởng EnglishLens.

Grounding DINO Tiny: khoảng 689 MB. RAM: khoảng 5.626 GB.
Các script tải theo phần có thể chạy lại để tiếp tục và kiểm tra SHA256 sau khi ghép file.
Không chạy nhiều script tải cùng một model cùng lúc.

```powershell
cd D:\Dow\EnglishLens
# Tải Grounding DINO và tokenizer trước:
.\.venv-ram\Scripts\python.exe .\fetch_dino_direct.py
# Tiếp tục tải RAM:
.\.venv-ram\Scripts\python.exe .\resume_ram.py
# Chạy UI thủ công:
.\.venv-ram\Scripts\python.exe .\app.py --open
# Chạy một ảnh:
.\run.ps1 .\vendor\recognize-anything\images\demo\demo1.jpg --labels "dog,couch,lamp"
```

Trong UI, model được giữ trong bộ nhớ để tránh nạp lại mỗi khung hình.
RAM bỏ các module sinh caption không dùng trước khi chuyển lên GPU.
Giảm độ phân giải ảnh xử lý cho camera; RAM và DINO vẫn có thể nhận nhầm/bỏ sót.

## Nguồn

- RAM: https://github.com/xinyu1205/recognize-anything — Apache-2.0 cho code.
  Giữ LICENSE và NOTICE.txt trong vendor/recognize-anything.
- RAM weights: https://huggingface.co/xinyu1205/recognize_anything_model — model card ghi MIT.
- Grounding DINO: https://huggingface.co/IDEA-Research/grounding-dino-tiny
- DINO chạy qua Transformers, không cần biên dịch CUDA extension.

## Tra từ và nghe phát âm

Bấm nhãn trên ảnh AI hoặc nút từ bên dưới để chỉ hiện bounding box của vật thể đó. App tạm dừng nhận diện liên tục khi chọn để giữ ảnh ổn định. Tra Dictionary API cần Internet; kết quả được lưu trong phiên trình duyệt. App ưu tiên audio API, có nút nghe lại; khi không có audio dùng được có thể dùng giọng đọc trình duyệt. Hiện tất cả khôi phục các box, ảnh mới xóa lựa chọn cũ.

## Kiểm thử camera

Khi chọn một vật thể ở chế độ **Tự tìm nhãn**, bảng từ vựng hiển thị confidence RAM thực tế từ cùng lượt suy luận, ngưỡng riêng của nhãn và điểm Grounding DINO. Điểm RAM thuộc nhãn trong toàn ảnh; điểm DINO thuộc box được chọn. Chế độ nhập nhãn không chạy RAM. Nếu nhãn DINO giải mã không khớp chính xác nhãn RAM, ứng dụng báo không có điểm khớp thay vì gán điểm của nhãn khác.

Chạy `.\.venv-ram\Scripts\python.exe -m unittest discover -s tests -v` để kiểm tra luồng MJPEG, ngắt/kết nối lại, xử lý khung hình chia nhỏ và so sánh FPS với cách lấy từng ảnh cũ. Bộ kiểm thử dùng camera giả lập 30 FPS trên localhost, không cần điện thoại, tải model hay Internet.
