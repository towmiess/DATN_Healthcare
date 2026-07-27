import sys
sys.path.insert(0, ".")
from uc_lib import HEAD, TAIL, actor, usecase, boundary, line, title

W, H = 1360, 880
svg = [HEAD.format(w=W, h=H)]
svg.append(title(W/2, 38, "SƠ ĐỒ USE CASE - MODULE CHATBOT TƯ VẤN (RAG-SERVICE)", 18))

BX, BY, BW, BH = 300, 80, 780, 740
svg.append(boundary(BX, BY, BW, BH, "CHATBOT TƯ VẤN RAG"))

a_user, _ = actor(110, 380, "Người dùng", 1.0)
a_admin, _ = actor(1250, 380, "Quản trị viên\\ntri thức", 1.0)
svg.append(a_user)
svg.append(a_admin)

RX, RY = 118, 38

# main + include/extend cluster (left/center of boundary)
uc_chat = (560, 170)
uc_history = (560, 320)
uc_remember = (560, 460)
uc_sync = (560, 600)

uc_session = (800, 170)      # include
uc_emergency = (860, 300)    # extend
uc_drug = (860, 430)         # extend

uc_manage_doc = (1000, 560)
uc_rebuild = (1000, 660)
uc_stats = (1000, 760) if False else None

svg.append(usecase(*uc_chat, RX, RY, ["Trò chuyện /", "Đặt câu hỏi tư vấn"], fs=13))
svg.append(usecase(*uc_history, RX, RY, ["Xem lịch sử", "hội thoại"], fs=13))
svg.append(usecase(*uc_remember, RX, RY, ["Ghi nhớ tri thức /", "quy tắc cá nhân"], fs=13))
svg.append(usecase(*uc_sync, RX, RY, ["Đồng bộ lịch sử", "chat đa thiết bị"], fs=13))

svg.append(usecase(*uc_session, 90, 30, ["Lấy phiên", "chat (Redis)"], fs=11))
svg.append(usecase(*uc_emergency, 95, 32, ["Xử lý câu hỏi", "khẩn cấp"], fs=11.5))
svg.append(usecase(*uc_drug, 95, 32, ["Tra cứu", "thông tin thuốc"], fs=11.5))

svg.append(usecase(*uc_manage_doc, 110, 34, ["Quản lý tài liệu", "tri thức (thêm/xóa)"], fs=11.5))
svg.append(usecase(*uc_rebuild, 110, 34, ["Lập lại chỉ mục", "(rebuild index)"], fs=11.5))

uc_admin_stats = (760, 700)
uc_clear_cache = (560, 700)
svg.append(usecase(*uc_admin_stats, 110, 34, ["Xem thống kê", "hệ thống RAG"], fs=11.5))
svg.append(usecase(*uc_clear_cache, 110, 34, ["Xóa cache", "LLM"], fs=11.5))

# actor associations
svg.append(line(140, 300, uc_chat[0]-RX, uc_chat[1]+10, color="#2F6FDE"))
svg.append(line(140, 340, uc_history[0]-RX, uc_history[1], color="#2F6FDE"))
svg.append(line(140, 400, uc_remember[0]-RX, uc_remember[1], color="#2F6FDE"))
svg.append(line(140, 440, uc_sync[0]-RX, uc_sync[1], color="#2F6FDE"))

svg.append(line(1220, 470, uc_manage_doc[0]+110, uc_manage_doc[1], color="#C0392B"))
svg.append(line(1220, 490, uc_rebuild[0]+110, uc_rebuild[1], color="#C0392B"))
svg.append(line(1220, 510, uc_admin_stats[0]+95, uc_admin_stats[1]-10, color="#C0392B"))
svg.append(line(1220, 530, uc_clear_cache[0]+95, uc_clear_cache[1]+5, color="#C0392B"))

# include relation
svg.append(line(uc_chat[0]+RX, uc_chat[1]+15, uc_session[0]-88, uc_session[1], dashed=True, arrow=True,
                 label="&lt;&lt;include&gt;&gt;", label_dx=10, label_dy=-8))
# extend relations
svg.append(line(uc_emergency[0]-93, uc_emergency[1], uc_chat[0]+RX, uc_chat[1]+40, dashed=True, arrow=True,
                 label="&lt;&lt;extend&gt;&gt;", label_dx=30, label_dy=10))
svg.append(line(uc_drug[0]-93, uc_drug[1], uc_chat[0]+RX, uc_chat[1]+55, dashed=True, arrow=True,
                 label="&lt;&lt;extend&gt;&gt;", label_dx=30, label_dy=20))

svg.append(TAIL)
with open("rag_uc.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print("done")
