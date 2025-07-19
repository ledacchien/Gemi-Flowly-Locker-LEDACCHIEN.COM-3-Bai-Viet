import streamlit as st
from streamlit.components.v1 import html
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from streamlit.errors import StreamlitAPIException, StreamlitSecretNotFoundError
import os
import glob

def rfile(name_file):
    """Hàm đọc nội dung từ file một cách an toàn."""
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception:
        return ""

# --- Đăng nhập bằng pass, đã sửa lỗi và tối ưu ---
def check_password():
    """
    Kiểm tra xem người dùng đã đăng nhập chưa.
    Nếu chưa, hiển thị biểu mẫu đăng nhập.
    Hàm này sẽ chặn thực thi phần còn lại của ứng dụng cho đến khi đăng nhập thành công.
    """
    password = rfile("password.txt")
    if not password:
        st.error("Lỗi: File `password.txt` chưa được thiết lập hoặc đang trống.")
        st.info("Vui lòng tạo file `password.txt` và nhập mật khẩu vào đó để tiếp tục.")
        st.stop()

    # Nếu người dùng đã được xác thực trong session, cho phép truy cập.
    if st.session_state.get("is_authenticated", False):
        return True

    # Hiển thị biểu mẫu đăng nhập.
    with st.form("login_form"):
        st.title("🔐 Đăng nhập")
        st.markdown("Vui lòng nhập mật khẩu để truy cập ứng dụng.")
        input_pass = st.text_input("Mật khẩu", type="password", key="password_input")
        submitted = st.form_submit_button("Đăng nhập")

        if submitted:
            if input_pass == password:
                st.session_state.is_authenticated = True
                # Tải lại ứng dụng để hiển thị nội dung chính sau khi đăng nhập thành công.
                st.rerun()
            else:
                st.error("Mật khẩu không chính xác. Vui lòng thử lại.")
    
    # Nếu đến đây, có nghĩa là người dùng chưa được xác thực và biểu mẫu đã được hiển thị.
    # Dừng thực thi để không hiển thị phần còn lại của ứng dụng.
    st.stop()

def load_config_data(config_file, default_data):
    """Tải dữ liệu cấu hình từ file, sử dụng giá trị mặc định nếu file không tồn tại hoặc thiếu dòng."""
    try:
        with open(config_file, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip() and not line.startswith('#')]
            while len(lines) < len(default_data):
                lines.append(default_data[len(lines)])
            return lines[:len(default_data)]
    except Exception:
        return default_data

@st.cache_data(ttl=600)
def get_all_products_as_dicts(folder_path="product_data"):
    """Lấy tất cả thông tin sản phẩm từ các file .txt và chuyển thành danh sách các dictionary."""
    product_index = []
    if not os.path.isdir(folder_path):
        return []
    file_paths = [f for f in glob.glob(os.path.join(folder_path, '*.txt')) if not os.path.basename(f) == '_link.txt']
    for file_path in file_paths:
        content = rfile(file_path)
        if not content:
            continue
        product_dict = {}
        for line in content.split('\n'):
            if ':' in line:
                key, value_str = line.split(':', 1)
                key_clean = key.strip().lower().replace(" ", "_")
                value_clean = value_str.strip()
                product_dict[key_clean] = value_clean
        product_dict['original_content'] = content
        if product_dict:
            product_index.append(product_dict)
    return product_index

def show_chatbot():
    """Hiển thị giao diện chatbot và xử lý logic."""
    google_api_key = None
    try:
        google_api_key = st.secrets.get("GOOGLE_API_KEY")
    except (StreamlitAPIException, StreamlitSecretNotFoundError):
        google_api_key = os.environ.get("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("Không tìm thấy Google API Key. Vui lòng thiết lập trong tệp .streamlit/secrets.toml (local) hoặc trong Config Vars (Heroku).")
        return

    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        st.error(f"Lỗi khi cấu hình Gemini API Key: {e}")
        return

    model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro-latest"
    base_system_prompt = rfile("system_data/01.system_trainning.txt")
    all_products_data = get_all_products_as_dicts()
    if all_products_data:
        product_data_string = "\nDưới đây là toàn bộ danh sách sản phẩm hệ thống mà bạn cần ghi nhớ để trả lời người dùng. Thông tin này là kiến thức nền của bạn:\n\n"
        for product in all_products_data:
            product_data_string += "--- BẮT ĐẦU SẢN PHẨM ---\n"
            product_data_string += product.get('original_content', '')
            product_data_string += "\n--- KẾT THÚC SẢN PHẨM ---\n\n"
        system_prompt = base_system_prompt + product_data_string
    else:
        system_prompt = base_system_prompt

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    )

    # Khởi tạo chat nếu chưa có trong session state
    if "chat" not in st.session_state or "messages" not in st.session_state:
        assistant_greeting = rfile("system_data/02.assistant.txt") or "Em kính chào anh/chị, Em là Flowly - Trợ lý AI Agent tại ledacchien.com. Anh/chị cần tư vấn về khóa học hoặc dịch vụ nào, em sẽ hỗ trợ ngay ạ!"
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.messages = [{"role": "assistant", "content": assistant_greeting}]

    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Xử lý input của người dùng
    if prompt := st.chat_input("Nhập nội dung trao đổi ở đây !"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")

def show_main_page():
    """Hiển thị nội dung trang chính."""
    st.subheader("✨ Các bài viết nổi bật")
    default_images = ["03bai_viet/article_images/pic1.jpg", "03bai_viet/article_images/pic2.jpg", "03bai_viet/article_images/pic3.jpg"]
    default_titles = ["Tiêu đề bài viết 1", "Tiêu đề bài viết 2", "Tiêu đề bài viết 3"]
    image_paths = [path if os.path.exists(path) else f"https://placehold.co/400x267/a3e635/44403c?text=Thiếu+ảnh+{i+1}" for i, path in enumerate(default_images)]
    article_titles = load_config_data("03bai_viet/config_titles.txt", default_titles)
    
    cols = st.columns(3, gap="medium")
    for i, col in enumerate(cols):
        with col:
            st.image(image_paths[i], use_container_width=True)
            if st.button(article_titles[i], use_container_width=True, key=f"btn{i+1}"):
                st.session_state.view = f"article_{i+1}"
                st.rerun()
                
    st.divider()
    if os.path.exists("system_data/logo.png"):
        logo_col1, logo_col2, logo_col3 = st.columns([1,1,1])
        with logo_col2:
            st.image("system_data/logo.png", use_container_width=True)
            
    st.markdown(f"<h2 style='text-align: center;'>{rfile('system_data/00.xinchao.txt') or 'Chào mừng đến với Trợ lý AI'}</h2>", unsafe_allow_html=True)
    show_chatbot()

def show_article_page(article_number):
    """Hiển thị trang chi tiết bài viết."""
    if st.button("⬅️ Quay về Trang chủ"): 
        st.session_state.view = "main"
        st.rerun()
    st.divider()
    try:
        with open(f"03bai_viet/bai_viet_0{article_number}.html", "r", encoding="utf-8") as f:
            html(f.read(), height=800, scrolling=True)
    except FileNotFoundError:
        st.error(f"Lỗi: Không tìm thấy file bài viết số {article_number}.")

def main():
    """Hàm chính chạy ứng dụng."""
    # st.set_page_config phải là lệnh Streamlit đầu tiên được gọi.
    st.set_page_config(page_title="Trợ lý AI", page_icon="🤖", layout="wide")
    
    # Yêu cầu đăng nhập bằng mật khẩu trước khi vào ứng dụng.
    check_password()
    
    with st.sidebar:
        st.title("⚙️ Tùy chọn")
        if st.button("🗑️ Xóa cuộc trò chuyện"):
            if "chat" in st.session_state: del st.session_state.chat
            if "messages" in st.session_state: del st.session_state.messages
            st.session_state.view = "main"
            st.rerun()
        st.divider()
        st.markdown("Một sản phẩm của [Lê Đắc Chiến](https://ledacchien.com)")

    # CSS tùy chỉnh
    st.markdown("""<style>
        /* Bắt buộc giao diện sáng */
        body {
            color: #31333F !important; /* Màu chữ chính */
            background-color: #FFFFFF !important; /* Màu nền chính */
        }
        [data-testid="stAppViewContainer"] {
            background-color: #FFFFFF !important;
        }
        [data-testid="stHeader"] {
            background-color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] > div:first-child {
             background-color: #F0F2F6 !important; /* Màu nền phụ */
        }
        /* Kết thúc bắt buộc giao diện sáng */

        [data-testid="stToolbar"], header, #MainMenu {visibility: hidden !important;}
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatMessageContent-user"]) { justify-content: flex-end; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent-user"]) { flex-direction: row-reverse; }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
            height: 150px;
            width: 100%;
            overflow: hidden;
            border-radius: 0.5rem;
        }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage img {
            height: 100%;
            width: 100%;
            object-fit: cover;
        }
        [data-testid="stChatMessages"] {
            min-height: 70vh;
        }
        @media (max-width: 768px) {
            .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
                height: 100px;
            }
            .stButton > button {
                font-size: 0.8rem;
                padding: 0.3em 0.5em;
            }
        }
    </style>""", unsafe_allow_html=True)

    # Điều hướng trang
    if "view" not in st.session_state: 
        st.session_state.view = "main"
        
    view_map = {
        "main": show_main_page, 
        "article_1": lambda: show_article_page(1), 
        "article_2": lambda: show_article_page(2), 
        "article_3": lambda: show_article_page(3)
    }
    view_map.get(st.session_state.view, show_main_page)()

if __name__ == "__main__":
    main()
import streamlit as st
from streamlit.components.v1 import html
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from streamlit.errors import StreamlitAPIException, StreamlitSecretNotFoundError
import os
import glob

def rfile(name_file):
    """Hàm đọc nội dung từ file một cách an toàn."""
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception:
        return ""

# --- Đăng nhập bằng pass, đã sửa lỗi và tối ưu ---
def check_password():
    """
    Kiểm tra xem người dùng đã đăng nhập chưa.
    Nếu chưa, hiển thị biểu mẫu đăng nhập.
    Hàm này sẽ chặn thực thi phần còn lại của ứng dụng cho đến khi đăng nhập thành công.
    """
    password = rfile("password.txt")
    if not password:
        st.error("Lỗi: File `password.txt` chưa được thiết lập hoặc đang trống.")
        st.info("Vui lòng tạo file `password.txt` và nhập mật khẩu vào đó để tiếp tục.")
        st.stop()

    # Nếu người dùng đã được xác thực trong session, cho phép truy cập.
    if st.session_state.get("is_authenticated", False):
        return True

    # Hiển thị biểu mẫu đăng nhập.
    with st.form("login_form"):
        st.title("🔐 Đăng nhập")
        st.markdown("Vui lòng nhập mật khẩu để truy cập ứng dụng.")
        input_pass = st.text_input("Mật khẩu", type="password", key="password_input")
        submitted = st.form_submit_button("Đăng nhập")

        if submitted:
            if input_pass == password:
                st.session_state.is_authenticated = True
                # Tải lại ứng dụng để hiển thị nội dung chính sau khi đăng nhập thành công.
                st.rerun()
            else:
                st.error("Mật khẩu không chính xác. Vui lòng thử lại.")
    
    # Nếu đến đây, có nghĩa là người dùng chưa được xác thực và biểu mẫu đã được hiển thị.
    # Dừng thực thi để không hiển thị phần còn lại của ứng dụng.
    st.stop()

def load_config_data(config_file, default_data):
    """Tải dữ liệu cấu hình từ file, sử dụng giá trị mặc định nếu file không tồn tại hoặc thiếu dòng."""
    try:
        with open(config_file, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip() and not line.startswith('#')]
            while len(lines) < len(default_data):
                lines.append(default_data[len(lines)])
            return lines[:len(default_data)]
    except Exception:
        return default_data

@st.cache_data(ttl=600)
def get_all_products_as_dicts(folder_path="product_data"):
    """Lấy tất cả thông tin sản phẩm từ các file .txt và chuyển thành danh sách các dictionary."""
    product_index = []
    if not os.path.isdir(folder_path):
        return []
    file_paths = [f for f in glob.glob(os.path.join(folder_path, '*.txt')) if not os.path.basename(f) == '_link.txt']
    for file_path in file_paths:
        content = rfile(file_path)
        if not content:
            continue
        product_dict = {}
        for line in content.split('\n'):
            if ':' in line:
                key, value_str = line.split(':', 1)
                key_clean = key.strip().lower().replace(" ", "_")
                value_clean = value_str.strip()
                product_dict[key_clean] = value_clean
        product_dict['original_content'] = content
        if product_dict:
            product_index.append(product_dict)
    return product_index

def show_chatbot():
    """Hiển thị giao diện chatbot và xử lý logic."""
    google_api_key = None
    try:
        google_api_key = st.secrets.get("GOOGLE_API_KEY")
    except (StreamlitAPIException, StreamlitSecretNotFoundError):
        google_api_key = os.environ.get("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("Không tìm thấy Google API Key. Vui lòng thiết lập trong tệp .streamlit/secrets.toml (local) hoặc trong Config Vars (Heroku).")
        return

    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        st.error(f"Lỗi khi cấu hình Gemini API Key: {e}")
        return

    model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro-latest"
    base_system_prompt = rfile("system_data/01.system_trainning.txt")
    all_products_data = get_all_products_as_dicts()
    if all_products_data:
        product_data_string = "\nDưới đây là toàn bộ danh sách sản phẩm hệ thống mà bạn cần ghi nhớ để trả lời người dùng. Thông tin này là kiến thức nền của bạn:\n\n"
        for product in all_products_data:
            product_data_string += "--- BẮT ĐẦU SẢN PHẨM ---\n"
            product_data_string += product.get('original_content', '')
            product_data_string += "\n--- KẾT THÚC SẢN PHẨM ---\n\n"
        system_prompt = base_system_prompt + product_data_string
    else:
        system_prompt = base_system_prompt

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    )

    # Khởi tạo chat nếu chưa có trong session state
    if "chat" not in st.session_state or "messages" not in st.session_state:
        assistant_greeting = rfile("system_data/02.assistant.txt") or "Em kính chào anh/chị, Em là Flowly - Trợ lý AI Agent tại ledacchien.com. Anh/chị cần tư vấn về khóa học hoặc dịch vụ nào, em sẽ hỗ trợ ngay ạ!"
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.messages = [{"role": "assistant", "content": assistant_greeting}]

    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Xử lý input của người dùng
    if prompt := st.chat_input("Nhập nội dung trao đổi ở đây !"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")

def show_main_page():
    """Hiển thị nội dung trang chính."""
    st.subheader("✨ Các bài viết nổi bật")
    default_images = ["03bai_viet/article_images/pic1.jpg", "03bai_viet/article_images/pic2.jpg", "03bai_viet/article_images/pic3.jpg"]
    default_titles = ["Tiêu đề bài viết 1", "Tiêu đề bài viết 2", "Tiêu đề bài viết 3"]
    image_paths = [path if os.path.exists(path) else f"https://placehold.co/400x267/a3e635/44403c?text=Thiếu+ảnh+{i+1}" for i, path in enumerate(default_images)]
    article_titles = load_config_data("03bai_viet/config_titles.txt", default_titles)
    
    cols = st.columns(3, gap="medium")
    for i, col in enumerate(cols):
        with col:
            st.image(image_paths[i], use_container_width=True)
            if st.button(article_titles[i], use_container_width=True, key=f"btn{i+1}"):
                st.session_state.view = f"article_{i+1}"
                st.rerun()
                
    st.divider()
    if os.path.exists("system_data/logo.png"):
        logo_col1, logo_col2, logo_col3 = st.columns([1,1,1])
        with logo_col2:
            st.image("system_data/logo.png", use_container_width=True)
            
    st.markdown(f"<h2 style='text-align: center;'>{rfile('system_data/00.xinchao.txt') or 'Chào mừng đến với Trợ lý AI'}</h2>", unsafe_allow_html=True)
    show_chatbot()

def show_article_page(article_number):
    """Hiển thị trang chi tiết bài viết."""
    if st.button("⬅️ Quay về Trang chủ"): 
        st.session_state.view = "main"
        st.rerun()
    st.divider()
    try:
        with open(f"03bai_viet/bai_viet_0{article_number}.html", "r", encoding="utf-8") as f:
            html(f.read(), height=800, scrolling=True)
    except FileNotFoundError:
        st.error(f"Lỗi: Không tìm thấy file bài viết số {article_number}.")

def main():
    """Hàm chính chạy ứng dụng."""
    # st.set_page_config phải là lệnh Streamlit đầu tiên được gọi.
    st.set_page_config(page_title="Trợ lý AI", page_icon="🤖", layout="wide")
    
    # Yêu cầu đăng nhập bằng mật khẩu trước khi vào ứng dụng.
    check_password()
    
    with st.sidebar:
        st.title("⚙️ Tùy chọn")
        if st.button("🗑️ Xóa cuộc trò chuyện"):
            if "chat" in st.session_state: del st.session_state.chat
            if "messages" in st.session_state: del st.session_state.messages
            st.session_state.view = "main"
            st.rerun()
        st.divider()
        st.markdown("Một sản phẩm của [Lê Đắc Chiến](https://ledacchien.com)")

    # CSS tùy chỉnh
    st.markdown("""<style>
        /* Bắt buộc giao diện sáng */
        body {
            color: #31333F !important; /* Màu chữ chính */
            background-color: #FFFFFF !important; /* Màu nền chính */
        }
        [data-testid="stAppViewContainer"] {
            background-color: #FFFFFF !important;
        }
        [data-testid="stHeader"] {
            background-color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] > div:first-child {
             background-color: #F0F2F6 !important; /* Màu nền phụ */
        }
        /* Kết thúc bắt buộc giao diện sáng */

        [data-testid="stToolbar"], header, #MainMenu {visibility: hidden !important;}
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatMessageContent-user"]) { justify-content: flex-end; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent-user"]) { flex-direction: row-reverse; }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
            height: 150px;
            width: 100%;
            overflow: hidden;
            border-radius: 0.5rem;
        }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage img {
            height: 100%;
            width: 100%;
            object-fit: cover;
        }
        [data-testid="stChatMessages"] {
            min-height: 70vh;
        }
        @media (max-width: 768px) {
            .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
                height: 100px;
            }
            .stButton > button {
                font-size: 0.8rem;
                padding: 0.3em 0.5em;
            }
        }
    </style>""", unsafe_allow_html=True)

    # Điều hướng trang
    if "view" not in st.session_state: 
        st.session_state.view = "main"
        
    view_map = {
        "main": show_main_page, 
        "article_1": lambda: show_article_page(1), 
        "article_2": lambda: show_article_page(2), 
        "article_3": lambda: show_article_page(3)
    }
    view_map.get(st.session_state.view, show_main_page)()

if __name__ == "__main__":
    main()
