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

## Bộ từ vựng và flashcard

- Chọn một vật thể trong kết quả nhận diện, bấm **Thêm vào bộ từ vựng**. Ứng dụng dùng Argos Translate trên máy để dịch nghĩa tiếng Việt và Free Dictionary API để lấy định nghĩa, phiên âm, câu ví dụ. Có thể sửa nghĩa/ghi chú tiếng Việt sau đó.
- Trong **Bộ từ vựng của tôi**, có thể tự thêm từ, tìm kiếm, sửa nghĩa, nghe phát âm hoặc xóa từ. Từ trùng được nhận biết không phân biệt chữ hoa/thường và khoảng trắng thừa.
- Bấm **Học flashcard** để bắt đầu lượt học với thứ tự ngẫu nhiên. Bấm thẻ (hoặc Enter khi thẻ được chọn) để xem nghĩa. **Học lại** đưa thẻ về cuối lượt; **Đã nhớ** bỏ thẻ khỏi lượt hiện tại. Có thể học lại toàn bộ khi hoàn thành.
- Bộ từ lưu trong localStorage của trình duyệt tại địa chỉ ứng dụng. Dùng cùng trình duyệt và địa chỉ `http://127.0.0.1:7860` để xem lại. Xóa dữ liệu trang hoặc dùng hồ sơ/trình duyệt khác sẽ không giữ cùng bộ từ. Tiến độ flashcard chỉ tính trong lượt học hiện tại.
- Flashcard và ghi chú đã lưu dùng được khi mất mạng. Phát âm ưu tiên audio từ Free Dictionary API; khi audio thiếu hoặc lỗi, dùng giọng tiếng Anh của trình duyệt/hệ điều hành.

## Lật ngang camera

Sau khi kết nối DroidCam hoặc webcam, bấm **Lật ngang camera** để bật/tắt chế độ hình gương. Cả hình trực tiếp và ảnh chụp gửi AI đều được lật nên bounding box khớp với ảnh nhận diện. Kết quả đã chụp trước đó được giữ nguyên; ảnh mẫu không bị lật. Đây là lật hình ngang, không phải chuyển camera trước/sau của điện thoại (việc chuyển camera thực hiện trong DroidCam).

## Kiểm thử giao diện mới

Cần Node.js và Microsoft Edge. Khi máy chủ ứng dụng đang chạy, thực hiện:

```powershell
npm install --prefix .cache/ui-tests --no-audit --no-fund playwright
node tests/vocabulary.browser.cjs
```

Kiểm thử dùng hồ sơ trình duyệt tạm, không sửa bộ từ đang dùng. Bao gồm lưu qua tải lại trang, chống trùng, sửa/xóa/tìm từ, thêm từ nhận diện, flashcard, pixel ảnh lật và bố cục di động. Ảnh kiểm tra giao diện nằm trong `outputs/vocabulary-desktop.png` và `outputs/vocabulary-mobile.png`.


## Dịch nghĩa, câu ví dụ và phát âm khi lưu từ

- Cả thêm từ thủ công và thêm từ từ ảnh đều gọi `/api/vocabulary?word=...`. Để trống ô nghĩa để tự dịch; nghĩa tự nhập được ưu tiên giữ lại.
- Nghĩa tiếng Việt được dịch offline bằng [Argos Translate](https://argos-translate.readthedocs.io/en/latest/), model Anh–Việt lưu tại `models/argos`. Dịch máy có thể chưa đúng ngữ cảnh; bạn có thể chỉnh sửa nghĩa.
- Định nghĩa, phiên âm và câu ví dụ lấy từ [Free Dictionary API](https://dictionaryapi.dev/). Ví dụ được chọn cùng định nghĩa tương ứng; nếu API không có ví dụ, ứng dụng báo rõ, không tự tạo câu rồi gán là dữ liệu API.
- Nút **Nghe** trong bộ từ và flashcard ưu tiên `/api/pronunciation`; lỗi audio sẽ chuyển sang giọng trình duyệt. Nội dung nghĩa và ví dụ đã lưu vẫn xem được khi không có mạng; audio API cần Internet.
- Với từ cũ hoặc cần cập nhật dữ liệu, bấm **Lấy lại API** tại từ đó. Nghĩa đã sửa thủ công được giữ nguyên. Dịch thành công được cache 24 giờ trong máy chủ để tránh dịch lại; khi lỗi vẫn lưu từ để bạn bổ sung hoặc thử lại sau.


## Cài model Argos Translate

Sau khi cài `requirements.txt`, chạy một lần (cần Internet để tải model):

```powershell
.\.venv-ram\Scripts\python.exe -X utf8 setup_argos.py
```

Các lần dịch sau chạy trên CPU tại máy, không gửi từ tới dịch vụ dịch thuật bên ngoài. Câu ví dụ và audio vẫn lấy từ Free Dictionary API nên cần Internet nếu chưa có cache. Từ đã lưu trước đây giữ nguyên nghĩa; dùng **Lấy lại API** để cập nhật bằng Argos, còn nghĩa tự sửa vẫn được giữ.

`requirements.txt` cố định CTranslate2 ở bản 4.4.0. Trên Windows với môi trường PyTorch 2.5.1+cu121 của project, bản CTranslate2 4.8.4 gây xung đột DLL cuDNN khi dịch rồi nhận diện, làm server thoát với lỗi `cudnnGetLibConfig`. Khi cập nhật từ bản cũ, chạy lại `pip install -r requirements.txt` bằng Python của `.venv-ram` và khởi động lại server.

Máy có GPU CUDA và đã cài model Argos có thể kiểm tra cả hai thứ tự nạp thư viện (dịch trước hoặc nhận diện trước):

```powershell
$env:ENGLISHLENS_RUNTIME_TESTS = '1'
.\.venv-ram\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
Remove-Item Env:ENGLISHLENS_RUNTIME_TESTS
```

Hai test tích hợp này mặc định được bỏ qua trên máy chưa có CUDA/model; các test còn lại không cần tải model.

Mặt trước flashcard hiển thị từ tiếng Anh. Khi lật, mặt sau chỉ hiển thị **nghĩa tiếng Việt và câu ví dụ**; không hiển thị từ tiếng Anh riêng, phiên âm hoặc định nghĩa tiếng Anh. Câu ví dụ giữ nguyên tiếng Anh do Dictionary API cung cấp.
