import re
import os
import json
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
# Danh sách Admin (thêm ID mới vào trong ngoặc, cách nhau dấu phẩy)
ADMIN_IDS = [507318519] 
LINK_NHOM = "https://t.me/+3VybdCszC1NmNTQ1" 
GROUP_ID = -1002946689229 
DATA_FILE = 'bot_data.json' # File để lưu giá
AUTO_DELETE_TIME = 60 # Thời gian tự xóa tin nhắn (giây). Để 0 nếu không muốn xóa.

# --- TỪ KHÓA BỎ QUA ---
TU_KHOA_BO_QUA = [
    'đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 
    'đã bank', 'đã chuyển', 'check giúp', 'kiểm tra giúp',
    'done', 'xong rồi', 'uy tín', 'cảm ơn', 'thanks', 'ok', 'oke'
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

# --- QUẢN LÝ DỮ LIỆU (LƯU/TẢI GIÁ) ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"rate": 27.0} # Giá mặc định nếu file lỗi hoặc chưa có

def save_data(rate):
    with open(DATA_FILE, 'w') as f:
        json.dump({"rate": rate}, f)

# Khởi tạo giá từ file
bot_data = load_data()
current_usd_rate = bot_data["rate"]

# --- SERVER ẢO (KEEP ALIVE) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return f"Bot đang chạy. Giá hiện tại: {current_usd_rate}"

def run_http():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- HELPER: TỰ XÓA TIN NHẮN ---
async def delete_later(context: ContextTypes.DEFAULT_TYPE, chat_id, message_id, delay=60):
    if delay <= 0: return
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass # Bỏ qua nếu tin nhắn đã bị xóa trước đó

# --- LOGIC BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("🇻🇳 BẤM VÀO ĐÂY ĐỂ CÀI TIẾNG VIỆT 🇻🇳", url="https://t.me/setlanguage/vi-beta")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        f"👋 Chào {user_name}!\n\n"
        f"Nếu Telegram của bạn đang là Tiếng Anh, hãy bấm vào nút bên dưới để chuyển sang giao diện **Tiếng Việt** ngay nhé 👇"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh chỉnh giá: /gia 26.95"""
    global current_usd_rate
    
    # Kiểm tra Admin trong danh sách
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bạn không có quyền đổi giá!")
        return

    try:
        if not context.args:
            await update.message.reply_text(f"ℹ️ Giá hiện tại: **{current_usd_rate}**. Gõ `/gia 26.95` để đổi.", parse_mode='Markdown')
            return
            
        raw_input = context.args[0].replace(',', '.') # Chấp nhận cả dấu phẩy
        new_rate = float(raw_input)
        
        # Tự động sửa nếu nhập nhầm (ví dụ nhập 27000 thay vì 27)
        if new_rate > 1000: new_rate = new_rate / 1000
        
        current_usd_rate = new_rate
        save_data(new_rate) # LƯU VÀO FILE
        
        display_rate = "{:,.3f}".format(new_rate).rstrip('0').rstrip('.')
        
        announcement = (
            f"📣 **THÔNG BÁO CẬP NHẬT TỶ GIÁ**\n"
            f"--------------------------------\n"
            f"💵 Giá USD hiện tại: **{display_rate}** VNĐ\n"
            f"✅ Áp dụng cho mọi giao dịch kể từ thời điểm này.\n\n"
            f"👉 Mời anh em lên đơn!"
        )
        
        try:
            # Gửi vào nhóm và ghim
            sent_message = await context.bot.send_message(chat_id=GROUP_ID, text=announcement, parse_mode='Markdown')
            try:
                await sent_message.pin()
            except:
                pass # Bỏ qua lỗi ghim nếu bot không đủ quyền
            
            await update.message.reply_text(f"✅ Đã cập nhật và lưu giá **{display_rate}** thành công!")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Đã lưu giá nhưng lỗi gửi vào nhóm: {e}")

    except ValueError:
        await update.message.reply_text("⚠️ Lỗi! Hãy nhập đúng số. Ví dụ: /gia 27.5")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return

    chat_type = update.message.chat.type 
    user_id = update.effective_user.id   
    text = update.message.text.lower()
    
    # 1. KIỂM TRA TIN NHẮN RIÊNG (DM)
    if chat_type == 'private' and user_id not in ADMIN_IDS:
        keyboard = [[InlineKeyboardButton("🇻🇳 BẤM ĐỂ CÀI TIẾNG VIỆT", url="https://t.me/setlanguage/vi-beta")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = (
            f"⛔ **BOT KHÔNG BÁO GIÁ RIÊNG!**\n\n"
            f"Mời bạn vào nhóm chung để giao dịch:\n"
            f"👉 **Tham gia ngay:** {LINK_NHOM}\n\n"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        return 
    
    # 2. BỘ LỌC TỪ KHÓA
    if any(tu_khoa in text for tu_khoa in TU_KHOA_BO_QUA):
        return 

    # 3. XỬ LÝ TÍNH TIỀN
    keywords = ['mua', 'bán', 'đổi', 'check', 'giá', 'usd', 'đô', '$', 'rate']
    
    # Regex tìm số (hỗ trợ số thập phân 10.5 hoặc 10,5)
    # Tìm pattern: Số + (dấu . hoặc ,) + Số
    match = re.search(r'(\d+[\.,]?\d*)', text)
    
    rate_display = "{:,.3f}".format(current_usd_rate).rstrip('0').rstrip('.')

    # Trường hợp 1: Có số lượng -> Tính tiền
    if match:
        raw_num = match.group(1).replace(',', '.')
        try:
            amount = float(raw_num)
        except:
            return # Không convert được thì bỏ qua

        # Logic lọc tin rác: Chỉ trả lời nếu tin nhắn ngắn hoặc có từ khóa
        should_reply = False
        is_pure_number = text.strip().replace('.', '').replace(',', '').replace('$', '').isdigit()
        
        if is_pure_number: should_reply = True
        elif any(word in text for word in keywords): should_reply = True

        if should_reply:
            total_vnd = amount * current_usd_rate * 1000 
            
            # Làm tròn tiền Việt cho gọn
            formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
            # Format số lượng USD hiển thị
            formatted_amount = "{:,.2f}".format(amount).rstrip('0').rstrip('.').replace('.', ',')
            
            response = (
                f"💵 **BÁO GIÁ:**\n"
                f"✅ Số lượng: {formatted_amount} $\n"
                f"✅ Tỷ giá: {rate_display}\n"
                f"💰 **THÀNH TIỀN: {formatted_vnd} VNĐ**\n"
                f"-----------------------------\n"
                f"{NOI_DUNG_CK}"
            )
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            photo_path = os.path.join(script_dir, 'qr.jpg') 

            sent_msg = None
            try:
                target_chat_id = update.message.chat_id
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo:
                        sent_msg = await context.bot.send_photo(chat_id=target_chat_id, photo=photo, caption=response, parse_mode='Markdown')
                else:
                    sent_msg = await context.bot.send_message(chat_id=target_chat_id, text=response, parse_mode='Markdown')
            except:
                sent_msg = await update.message.reply_text(response, parse_mode='Markdown')
            
            # Tự động xóa tin nhắn sau AUTO_DELETE_TIME
            if sent_msg and AUTO_DELETE_TIME > 0:
                asyncio.create_task(delete_later(context, sent_msg.chat_id, sent_msg.message_id, delay=AUTO_DELETE_TIME))


    # Trường hợp 2: Hỏi giá chơi (không có số)
    elif any(word in text for word in keywords):
        response_rate = (
            f"📈 **CẬP NHẬT TỶ GIÁ HÔM NAY:**\n"
            f"-----------------------------\n"
            f"💵 Giá USD: **{rate_display}** VNĐ\n"
            f"*(Nhập số lượng cụ thể để nhận báo giá chi tiết)*"
        )
        msg = await update.message.reply_text(response_rate, parse_mode='Markdown')
        # Cũng tự xóa thông báo giá chơi
        if AUTO_DELETE_TIME > 0:
            asyncio.create_task(delete_later(context, msg.chat_id, msg.message_id, delay=30))

def main():
    keep_alive() 
    print("Bot đang chạy...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("tiengviet", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    
    # Handler tin nhắn
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()
