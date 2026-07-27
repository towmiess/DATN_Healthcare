import sys
sys.path.insert(0, ".")
from uc_lib import HEAD, TAIL, actor, usecase, boundary, line, title

W, H = 1500, 1060
svg = [HEAD.format(w=W, h=H)]

svg.append(title(W/2, 40, "SƠ ĐỒ USE CASE TỔNG QUÁT - HỆ THỐNG HEALTHCARE DIABETES", 19))

BX, BY, BW, BH = 220, 80, 1000, 900
svg.append(boundary(BX, BY, BW, BH, "HỆ THỐNG HEALTHCARE DIABETES"))

# actors
a_user_svg, _ = actor(90, 485, "Người dùng", 1.0)
a_admin_svg, _ = actor(1400, 485, "Quản trị viên", 1.0)
svg.append(a_user_svg)
svg.append(a_admin_svg)

cols_x = [340, 570, 800, 1030]
rows_y = [170, 335, 500, 665, 830]
RX, RY = 100, 34

col1 = [
    ["Đăng ký", "tài khoản"],
    ["Đăng nhập /", "Đăng xuất"],
    ["Quên mật khẩu", "(qua OTP email)"],
    ["Cập nhật hồ sơ", "sức khỏe"],
    ["Nhập / OCR chỉ số", "đường huyết"],
]
col2 = [
    ["Dự đoán nguy cơ", "tiểu đường/tim mạch/", "đột quỵ"],
    ["Xem gợi ý", "món ăn"],
    ["Lập kế hoạch", "bữa ăn theo ngày"],
    ["Phân tích ảnh bữa ăn", "(AI Vision)"],
    ["Xem lịch sử", "bữa ăn"],
]
col3 = [
    ["Trò chuyện với", "Chatbot tư vấn (RAG)"],
    ["Quản lý", "nhắc nhở"],
    ["Xem thông báo", "(realtime)"],
    ["Xem báo cáo &amp;", "AI Insight"],
    None,
]
col4 = [
    ["Quản lý", "người dùng"],
    ["Quản lý nguyên liệu", "&amp; món ăn"],
    ["Theo dõi &amp; xử lý", "job AI Vision"],
    ["Quản lý kho", "tri thức RAG"],
    ["Xem trạng thái", "vận hành hệ thống"],
]

all_cols = [col1, col2, col3, col4]
positions = {}
for ci, col in enumerate(all_cols):
    for ri, lines in enumerate(col):
        if lines is None:
            continue
        cx, cy = cols_x[ci], rows_y[ri]
        positions[(ci, ri)] = (cx, cy)
        svg.append(usecase(cx, cy, RX, RY, lines, fs=12.5))

# connect user actor to col1, col2, col3 use cases
user_pt = (110, 500)
for ci in [0, 1, 2]:
    for ri in range(5):
        if (ci, ri) in positions:
            cx, cy = positions[(ci, ri)]
            svg.append(line(user_pt[0], user_pt[1], cx - RX, cy, color="#2F6FDE"))

# connect admin actor to col4 use cases
admin_pt = (1400, 500)
for ri in range(5):
    if (3, ri) in positions:
        cx, cy = positions[(3, ri)]
        svg.append(line(admin_pt[0], admin_pt[1], cx + RX, cy, color="#C0392B"))

svg.append(TAIL)

with open("overview_uc.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print("done")
