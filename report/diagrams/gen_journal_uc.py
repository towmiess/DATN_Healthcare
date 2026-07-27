import sys
sys.path.insert(0, ".")
from uc_lib import HEAD, TAIL, actor, usecase, boundary, line, title

W, H = 1300, 760
svg = [HEAD.format(w=W, h=H)]
svg.append(title(W/2, 38, "SƠ ĐỒ USE CASE - NHẬT KÝ SỨC KHỎE &amp; BÁO CÁO AI INSIGHT", 17))

BX, BY, BW, BH = 260, 80, 780, 620
svg.append(boundary(BX, BY, BW, BH, "NHẬT KÝ SỨC KHỎE &amp; BÁO CÁO AI INSIGHT"))

a_user, _ = actor(110, 340, "Người dùng", 1.0)
svg.append(a_user)

RX, RY = 118, 36

uc_write = (520, 160)
uc_analyze = (800, 160)   # include
uc_alert = (860, 300)     # extend

uc_history = (520, 300)
uc_dashboard = (520, 440)
uc_insight = (800, 440)    # include
uc_export = (520, 580)
uc_draft = (800, 580)

svg.append(usecase(*uc_write, RX, RY, ["Ghi nhật ký", "sức khỏe"], fs=13))
svg.append(usecase(*uc_analyze, 95, 32, ["Phân tích nhật ký", "bằng AI"], fs=11.5))
svg.append(usecase(*uc_alert, 95, 32, ["Cảnh báo mức", "cần lưu ý cao"], fs=11.5))

svg.append(usecase(*uc_history, RX, RY, ["Xem lịch sử nhật ký", "&amp; kết quả phân tích"], fs=12.5))
svg.append(usecase(*uc_dashboard, RX, RY, ["Xem báo cáo sức khỏe", "(dashboard tuần/tháng)"], fs=12))
svg.append(usecase(*uc_insight, 95, 32, ["Tạo AI Insight", "giải thích tình trạng"], fs=11.5))
svg.append(usecase(*uc_export, RX, RY, ["Export báo cáo", "(PDF/CSV)"], fs=13))
svg.append(usecase(*uc_draft, 95, 32, ["Lưu báo cáo", "nháp (draft)"], fs=12))

# actor associations
svg.append(line(140, 260, uc_write[0]-RX, uc_write[1]+10, color="#2F6FDE"))
svg.append(line(140, 300, uc_history[0]-RX, uc_history[1], color="#2F6FDE"))
svg.append(line(140, 380, uc_dashboard[0]-RX, uc_dashboard[1]-10, color="#2F6FDE"))
svg.append(line(140, 460, uc_export[0]-RX, uc_export[1]+5, color="#2F6FDE"))

# include: write -> analyze
svg.append(line(uc_write[0]+RX, uc_write[1], uc_analyze[0]-88, uc_analyze[1], dashed=True, arrow=True,
                 label="&lt;&lt;include&gt;&gt;", label_dx=10, label_dy=-10))
# extend: alert -> analyze
svg.append(line(uc_alert[0]-93, uc_alert[1], uc_analyze[0]+40, uc_analyze[1]+35, dashed=True, arrow=True,
                 label="&lt;&lt;extend&gt;&gt;", label_dx=30, label_dy=15))
# include: dashboard -> insight
svg.append(line(uc_dashboard[0]+RX, uc_dashboard[1]-5, uc_insight[0]-88, uc_insight[1]-5, dashed=True, arrow=True,
                 label="&lt;&lt;include&gt;&gt;", label_dx=10, label_dy=-10))
# include: export -> draft (just a relation showing draft can be exported) -- extend instead
svg.append(line(uc_export[0]+RX, uc_export[1]-5, uc_draft[0]-88, uc_draft[1]-5, dashed=True, arrow=True,
                 label="&lt;&lt;extend&gt;&gt;", label_dx=10, label_dy=-10))

svg.append(TAIL)
with open("journal_insight_uc.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print("done")
