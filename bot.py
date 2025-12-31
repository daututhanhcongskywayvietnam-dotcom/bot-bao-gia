import re 
import os 
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
ADMIN_ID = 507318519
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 

# --- TỪ KHÓA BỎ QUA ---
TU_KHOA_BO_QUA = [
    'đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 
    'đã bank', 'đã chuyển', 'check giúp', 'kiểm tra giúp',
    'done', 'xong rồi', 'uy tín', 'cảm ơn', 'thanks'
]

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
📝 **Nội dung chuyển khoản:** GHI SĐT CỦA BẠN

❌ **TUYỆT ĐỐI KHÔNG GHI:** Mua bán, USD, Tiền hàng...
📌 **Lưu ý quan trọng:** Chỉ giao dịch tài khoản chính chủ. Người mua chịu trách nhiệm 100% về nguồn tiền nếu xảy ra vấn đề pháp lý.
"""

# Giá mặc định
current_usd_rate = 27.0

# --- SERVER ẢO ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot đang chạy ngon lành!"

def run_http():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- LOGIC BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start hoặc /tiengviet: Gửi nút cài tiếng Việt"""
    user_name = update.effective_user.first_name
    
    # Tạo nút bấm (Link dẫn đến gói ngôn ngữ Tiếng Việt phổ biến nhất)
    keyboard = [
        [InlineKeyboardButton("🇻🇳 BẤM VÀO ĐÂY ĐỂ CÀI TIẾNG VIỆT 🇻🇳", url="https://t.me/setlanguage/vi-beta")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        f"👋 Chào {user_name}!\n\n"
        f"Nếu Telegram của bạn đang là Tiếng Anh và bạn thấy khó sử dụng, hãy bấm vào nút bên dưới để chuyển sang giao diện **Tiếng Việt** ngay nhé 👇"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chỉnh giá: /gia 26,95"""
    global current_usd_rate
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền đổi giá!")
        return

    try:
        if not context.args:
            await update.message.reply_text(f"ℹ️ Giá hiện tại: {current_usd_rate}. Gõ /gia 26,95 để đổi.")
            return
            
        raw_input = context.args[0].replace(',', '.')
        new_rate = float(raw_input)
        if new_rate > 1000: new_rate = new_rate / 1000
        current_usd_rate = new_rate
        display_rate = "{:,.3f}".format(new_rate).rstrip('0').rstrip('.')
        
        announcement = (
            f"📣 **THÔNG BÁO CẬP NHẬT TỶ GIÁ**\n"
            f"--------------------------------\n"
            f"💵 Giá USD hiện tại: **{display_rate}** VNĐ\n"
            f"✅ Áp dụng cho mọi giao dịch kể từ thời điểm này.\n\n"
            f"👉 Mời anh em lên đơn!"
        )
        
        try:
            sent_message = await context.bot.send_message(chat_id=GROUP_ID, text=announcement, parse_mode='Markdown')
            await sent_message.pin() 
            await update.message.reply_text(f"✅ Đã đăng bài và ghim giá **{display_rate}** lên nhóm thành công!")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Đã gửi nhưng LỖI GHIM: {e}")

    except ValueError:
        await update.message.reply_text("⚠️ Lỗi! Hãy nhập đúng số. Ví dụ: /gia 27")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type 
    user_id = update.effective_user.id   
    text = update.message.text.lower()
    
    # 1. KIỂM TRA TIN NHẮN RIÊNG
    if chat_type == 'private' and user_id != ADMIN_ID:
        # Nếu khách chat riêng, gửi lời chào + Nút cài Tiếng Việt luôn cho tiện
        keyboard = [
            [InlineKeyboardButton("🇻🇳 BẤM ĐỂ CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = (
            f"⛔ **BOT KHÔNG BÁO GIÁ RIÊNG!**\n\n"
            f"Mời bạn vào nhóm chung để giao dịch:\n"
            f"👉 **Tham gia ngay:** {LINK_NHOM}\n\n"
            f"👇 *Nếu chưa có Tiếng Việt, bấm nút dưới:*"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        return 
    
    # 2. BỘ LỌC TỪ KHÓA
    if any(tu_khoa in text for tu_khoa in TU_KHOA_BO_QUA):
        return 

    # 3. XỬ LÝ TÍNH TIỀN
    keywords = ['mua', 'bán', 'đổi', 'check', 'giá', 'usd', 'đô', '$', 'rate']
    clean_text = text.replace('.', '').replace(',', '')
    match = re.search(r'\d+', clean_text) 
    rate_display = "{:,.2f}".format(current_usd_rate).replace('.', ',')

    # Trường hợp 1: Có số lượng -> Tính tiền + Gửi QR
    if match:
        amount = int(match.group()) 
        should_reply = False
        if text.strip().replace('.', '').replace(',', '').replace('$', '').isdigit(): should_reply = True
        elif any(word in text for word in keywords): should_reply = True

        if should_reply:
            total_vnd = amount * current_usd_rate * 1000 
            formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
            
            response = (
                f"💵 **BÁO GIÁ:**\n"
                f"✅ Số lượng: {amount} $\n"
                f"✅ Tỷ giá: {rate_display}\n"
                f"💰 **THÀNH TIỀN: {formatted_vnd} VNĐ**\n"
                f"-----------------------------\n"
                f"{NOI_DUNG_CK}"
            )
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            photo_path = os.path.join(script_dir, 'qr.jpg') 

            try:
                target_chat_id = update.message.chat_id
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=target_chat_id, photo=photo, caption=response, parse_mode='Markdown')
                else:
                    await context.bot.send_message(chat_id=target_chat_id, text=response, parse_mode='Markdown')
            except:
                await update.message.reply_text(response, parse_mode='Markdown')

    # Trường hợp 2: Hỏi giá chơi
    elif any(word in text for word in keywords):
        response_rate = (
            f"📈 **CẬP NHẬT TỶ GIÁ HÔM NAY:**\n"
            f"-----------------------------\n"
            f"💵 Giá USD: **{rate_display}** VNĐ\n"
            f"*(Nhập số lượng cụ thể để nhận báo giá chi tiết)*"
        )
        await update.message.reply_text(response_rate, parse_mode='Markdown')

def main():
    keep_alive() 
    print("Bot đang chạy...")
    app = Application.builder().token(TOKEN).build()
    
    # Thêm lệnh /start và /tiengviet
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tiengviet", start_command))
    
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
