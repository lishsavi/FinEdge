import streamlit as st
import pandas as pd
import datetime
import mysql.connector

# -----------------------------
# 0. DATABASE CONNECTION
# -----------------------------
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",          # Change to your MySQL username
        password="",          # Change to your MySQL password
        database="ceylon_trade"
    )

def execute_query(query, params=(), fetch=False):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    result = None
    if fetch:
        result = cursor.fetchall()
    conn.commit()
    cursor.close()
    conn.close()
    return result

# -----------------------------
# 1. DATA MODELS
# -----------------------------
class Message:
    def __init__(self, sender, receiver, product_name, text, timestamp=None, id=None):
        self.id = id
        self.sender = sender
        self.receiver = receiver
        self.product_name = product_name
        self.text = text
        self.timestamp = timestamp or datetime.datetime.now().strftime("%I:%M %p")

class Product:
    def __init__(self, name, certifications, price, qty, unit, producer, image_url=None, note="", id=None):
        self.id = id or str(datetime.datetime.now().timestamp()) + name
        self.name = name
        self.certifications = certifications if isinstance(certifications, list) else (certifications.split(',') if certifications else [])
        self.price = float(price)
        self.qty = int(qty)
        self.unit = unit  
        self.producer = producer
        self.note = note 
        self.image_url = image_url if image_url and image_url.strip() != "" else "https://images.unsplash.com/photo-1594631252845-29fc4586c55c"

class User:
    def __init__(self, email, password, role):
        self.email = email
        self.password = password
        self.role = role

class Order:
    def __init__(self, product_id, product_name, qty, unit, total, buyer, producer, id=None, timestamp=None, rating=0, review=""):
        self.id = id or str(datetime.datetime.now().timestamp()) + buyer + product_name
        self.product_id = product_id
        self.product_name = product_name
        self.qty = int(qty)
        self.unit = unit 
        self.total = float(total)
        self.buyer = buyer
        self.producer = producer
        self.timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d | %I:%M %p")
        self.rating = int(rating)      
        self.review = review      

# -----------------------------
# 2. RULE-BASED CHATBOT LOGIC
# -----------------------------
class ExportAssistant:
    def __init__(self):
        self.knowledge_base = {
            "greetings": "Hi there! I am your Ceylon Trade assistant. I can guide you through Sri Lanka's export regulations and documentation. How can I help?",
            "registrations": """To export commercially, mandatory registrations include:
1. **Registrar of Companies**: Obtain your Business Registration Certificate (BRC).
2. **Inland Revenue (IRD)**: Register for your Tax Identification Number (TIN) and VAT.
3. **Sri Lanka Customs**: Register in the ASYCUDA system (requires TIN/BRC).
4. **Export Development Board (EDB)**: Official registration as an exporter (approx. LKR 10,000).""",
            "tea": """**Tea Export Requirements:**
- Mandatory registration with the **Sri Lanka Tea Board (SLTB)**.
- Adherence to **ISO 3720** standards.
- Must obtain a 'Quality Certificate' for every shipment.
- For exports to **Iran**, GMP (Good Manufacturing Practices) certification is mandatory.""",
            "spices": """**Spices & Cinnamon Requirements:**
- Requires a **Phytosanitary Certificate** from the National Plant Quarantine Service (NPQS).
- Inspection by the **Department of Export Agriculture**.
- Specific licenses are required to use the 'Pure Ceylon Cinnamon' branding/logo.""",
            "coconut": """**Coconut Product Requirements:**
- Registration with the **Coconut Development Authority (CDA)** is mandatory.
- Storage standards: Desiccated coconut must be stored 1m away from walls and stacked no higher than 10 bags.""",
            "coffee": """**Coffee Export Requirements:**
- Roasted coffee must use packaging with **one-way degassing valves**.
- Requires Phytosanitary or Health Certificates depending on the destination country's regulations.""",
            "handicrafts": """**Handicraft & Wood Exports:**
- Wooden items must be fully seasoned/dry.
- May require a **Timber Transport Permit** from relevant authorities.
- Packaging: Use bubble wrap for fragile items and silica gel for moisture control.""",
            "documents": """**Mandatory Shipping Documents:**
- **Commercial Invoice**: Product details, price, and terms.
- **Packing List**: Breakdown of each package.
- **Bill of Lading / Airway Bill**: Contract of carriage from the carrier.
- **Customs Declaration (CusDec)**: Submitted electronically via ASYCUDA.""",
            "certificates": """**Common Certificates Required:**
- **Phytosanitary Certificate**: From NPQS (for plants/spices).
- **Health Certificate**: From FCAU (for food products).
- **Certificate of Origin (COO)**: Preferential (Dept. of Commerce) or Non-Preferential (Chamber of Commerce).""",
            "costs": "Current estimated costs: EDB Registration (~LKR 10,000), SLTB Registration (~LKR 10,000 + VAT), and Customs Processing Fee (~LKR 550 per CusDec).",
            "process": """**The 3-Phase Export Flow:**
**Phase A (Preparation)**: Finalize sales contract, obtain product-specific quality certificates, and book freight.
**Phase B (Customs)**: Submit CusDec via ASYCUDA, pay levies/CESS, and undergo physical examination at the Export Facilitation Centre.
**Phase C (Post-Shipment)**: Collect Bill of Lading and apply for the Certificate of Origin (COO)."""
        }

    def get_response(self, query):
        query = query.lower().strip()
        if any(word in query for word in ["hi", "hello", "hey", "morning", "afternoon"]):
            return self.knowledge_base["greetings"]
        if any(word in query for word in ["register", "registration", "tin", "brc", "edb"]):
            return self.knowledge_base["registrations"]
        elif "tea" in query: return self.knowledge_base["tea"]
        elif any(word in query for word in ["spice", "cinnamon", "pepper"]): return self.knowledge_base["spices"]
        elif "coconut" in query: return self.knowledge_base["coconut"]
        elif "coffee" in query: return self.knowledge_base["coffee"]
        elif any(word in query for word in ["handicraft", "wood", "wooden", "furniture"]): return self.knowledge_base["handicrafts"]
        elif any(word in query for word in ["document", "invoice", "cusdec", "paperwork", "packing list"]): return self.knowledge_base["documents"]
        elif any(word in query for word in ["certificat", "sls", "iso", "health", "origin", "coo", "npqs"]): return self.knowledge_base["certificates"]
        elif any(word in query for word in ["cost", "price", "fee", "lkr", "payment"]): return self.knowledge_base["costs"]
        elif any(word in query for word in ["process", "steps", "flow", "phases", "how to"]): return self.knowledge_base["process"]
        return "I'm sorry, I don't have details on that specific query. Try asking about 'Tea standards', 'Customs process', 'Mandatory documents', or 'Registration costs'."


# -----------------------------
# 2. DASHBOARD LOGIC
# -----------------------------
class Dashboard:
    def __init__(self):
        self.primary_teal = "#197868"
        self.accent_teal = "#396662"
        self.inside_bg = "https://i.postimg.cc/rwCnjbPz/Gemini-Generated-Image-calz92calz92calz.png"
        self.assistant = ExportAssistant()

    def apply_ui_theme(self):
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("{self.inside_bg}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .stTextInput>div>div>input, 
            .stTextArea>div>div>textarea, 
            .stSelectbox>div>div>div,
            .stNumberInput>div>div>input {{
                border: 2px solid black !important;
                border-radius: 8px !important;
                color: black !important;
                background-color: white !important;
            }}
            h1, h2, h3 {{
                color: {self.primary_teal} !important;
                font-family: 'Segoe UI', sans-serif;
                font-weight: 700;
            }}
            .stButton>button {{
                background-color: {self.primary_teal} !important;
                color: white !important;
                border-radius: 10px !important;
                border: none !important;
                transition: 0.3s;
            }}
            .stButton>button:hover {{
                background-color: {self.accent_teal} !important;
                transform: translateY(-2px);
            }}
            /* Updated this block to match the green theme instead of red */
            div[data-testid="stHorizontalBlock"] div:last-child .stButton>button {{
                background-color: {self.primary_teal} !important;
            }}
            section[data-testid="stSidebar"] {{
                background-color: rgba(30, 86, 49, 0.05);
            }}
            .preserve-lines {{
                white-space: pre-wrap !important;
                word-wrap: break-word !important;
                font-family: inherit;
                line-height: 1.6;
            }}
            </style>
            """, unsafe_allow_html=True)

    def landing_page(self):
        bg_image_url = "https://i.postimg.cc/vZdzRjxX/Whats-App-Image-2026-03-13-at-19-11-08.jpg"
        st.markdown(f"""
            <style>
            .stApp {{ background-image: url("{bg_image_url}"); background-size: cover; background-position: center; }}
            .stApp::before {{
                content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.3); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); z-index: -1;
            }}
            .glass-header {{
                background: rgba(255, 255, 255, 0.92); padding: 40px; border-radius: 25px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3); text-align: center; margin-top: 50px;
            }}
            .header-title {{ color: #197868 !important; font-size: 70px !important; font-weight: 800 !important; margin: 0; }}
            .header-subtitle {{ color: #396662 !important; font-weight: 600 !important; font-size: 24px !important; }}
            </style>
            <div class="glass-header">
                <h1 class="header-title"> Ceylon Trade</h1>
                <h3 class="header-subtitle">A Digital Platform for Sri Lankan Export Growth</h3>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 6, 1])
        with col_mid:
            st.markdown("<div style='text-align: center; color: white; background: rgba(0,0,0,0.6); padding: 20px; border-radius: 15px; margin-bottom: 20px;'><p style='margin: 0; font-weight: bold; font-size: 18px;'>Empowering Local Producers, Craftsmen, and Rural Farmers.</p></div>", unsafe_allow_html=True)
            if st.button("🚀 Enter Marketplace", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()

    def login_page(self):
        self.apply_ui_theme()
        st.title("🔐 Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Producer", "Trader"])
        
        if st.button("Login", use_container_width=True):
            user = execute_query("SELECT * FROM Users WHERE email=%s AND password=%s AND role=%s", (email, password, role), fetch=True)
            if user:
                st.session_state.logged_in = True
                st.session_state.email = email
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid credentials.")
                
        if st.button("New here? Create Account"):
            st.session_state.page = "register"
            st.rerun()

    def register_page(self):
        self.apply_ui_theme()
        st.title("📝 Register")
        email = st.text_input("New Email")
        password = st.text_input("New Password", type="password")
        role = st.selectbox("I am a...", ["Producer", "Trader"])
        if st.button("Register Now", use_container_width=True):
            try:
                execute_query("INSERT INTO Users (email, password, role) VALUES (%s, %s, %s)", (email, password, role))
                st.success("Account created! Please login.")
                st.session_state.page = "login"
                st.rerun()
            except Exception as e:
                st.error("Error creating account. Email might already exist.")

    def render_messaging_center(self):
        st.subheader("📬 Conversations")
        me = st.session_state.email
        
        msgs = execute_query("SELECT * FROM Messages WHERE sender=%s OR receiver=%s", (me, me), fetch=True)
        messages = [Message(**m) for m in msgs]
        
        threads = []
        for m in messages:
            other = m.receiver if m.sender == me else m.sender
            thread_id = (other, m.product_name)
            if thread_id not in threads:
                threads.append(thread_id)

        if not threads:
            st.info("No messages yet.")
            return

        col_list, col_view = st.columns([1, 2])
        with col_list:
            st.write("**Recent Inquiries**")
            for i, (other, prod) in enumerate(threads):
                if st.button(f"👤 {other}\n\n📦 {prod}", key=f"t_btn_{i}", use_container_width=True):
                    st.session_state.active_thread = (other, prod)

        with col_view:
            if "active_thread" in st.session_state:
                other_party, prod_name = st.session_state.active_thread
                st.markdown(f"### Chat: {prod_name}")
                history = [m for m in messages if (m.sender == me and m.receiver == other_party and m.product_name == prod_name) or (m.sender == other_party and m.receiver == me and m.product_name == prod_name)]
                
                chat_container = st.container(height=350)
                for msg in history:
                    with chat_container.chat_message("user" if msg.sender == me else "assistant"):
                        st.write(msg.text)
                        st.caption(msg.timestamp)
                        
                if prompt := st.chat_input("Type your reply..."):
                    new_msg = Message(me, other_party, prod_name, prompt)
                    execute_query("INSERT INTO Messages (sender, receiver, product_name, text, timestamp) VALUES (%s, %s, %s, %s, %s)", 
                                  (new_msg.sender, new_msg.receiver, new_msg.product_name, new_msg.text, new_msg.timestamp))
                    st.rerun()
            else:
                st.info("Select a thread to view the conversation.")

    def producer_dashboard(self):
        self.apply_ui_theme()
        st.title("👨‍🌾 Producer Panel")
        
        if st.session_state.get("editing_product_id"):
            st.warning("⚠️ **Editing Mode Active** ")
        
        my_orders_data = execute_query("SELECT * FROM Orders WHERE producer=%s", (st.session_state.email,), fetch=True)
        my_products_data = execute_query("SELECT * FROM Products WHERE producer=%s", (st.session_state.email,), fetch=True)
        
        all_my_rated_orders = [Order(**o) for o in my_orders_data if o['rating'] > 0]
        my_products = [Product(**p) for p in my_products_data]

        m1, m2, m3 = st.columns(3)
        if all_my_rated_orders:
            avg_rating = sum(o.rating for o in all_my_rated_orders) / len(all_my_rated_orders)
            m1.metric("Reputation", f"{avg_rating:.1f} / 5 ⭐")
            m2.metric("Reviews", len(all_my_rated_orders))
        else:
            m1.metric("Reputation", "No ratings")
            m2.metric("Reviews", "0")
        
        m3.metric("Live Products", len(my_products))
        st.divider()

        tab_titles = ["➕ Add/Edit Product", "📦 Current Inventory", "📊 Sales & Reviews", "💬 Messages", "🤖 Export Assistant"]
        tabs = st.tabs(tab_titles)
        
        with tabs[0]:
            is_editing = st.session_state.get("editing_product_id") is not None
            product_to_edit = None
            if is_editing:
                product_to_edit = next((p for p in my_products if p.id == st.session_state.editing_product_id), None)
                st.info(f"Currently editing: **{product_to_edit.name if product_to_edit else 'Unknown'}**")
                if st.button("Cancel Edit"):
                    st.session_state.editing_product_id = None
                    st.rerun()

            with st.form("product_form", clear_on_submit=not is_editing):
                st.subheader("Product Details")
                default_name = product_to_edit.name if is_editing else ""
                default_note = product_to_edit.note if is_editing else ""
                default_img = product_to_edit.image_url if is_editing else ""
                default_certs = product_to_edit.certifications if is_editing else []
                default_price = float(product_to_edit.price) if is_editing else 0.1
                default_qty = int(product_to_edit.qty) if is_editing else 1
                
                name = st.text_input("Product Name", value=default_name)
                product_note = st.text_area("Product Descriptions / Features (Enter one by one line)", value=default_note, height=200)
                img_url = st.text_input("Image URL (Link)", value=default_img)
                certifications = st.multiselect("Certifications", ["SLS", "ISO 22000", "HACCP", "GMP"], default=default_certs)
                
                c1, c2, c3 = st.columns([2, 2, 1])
                price = c1.number_input("Price ($)", min_value=0.1, value=default_price)
                qty = c2.number_input("Stock Amount", min_value=0, value=default_qty)
                unit_options = ["kg", "pcs", "liters", "boxes", "mt"]
                default_unit_idx = unit_options.index(product_to_edit.unit) if is_editing and product_to_edit.unit in unit_options else 0
                unit = c3.selectbox("Unit", unit_options, index=default_unit_idx)
                
                submit_label = "Update Listing" if is_editing else "Publish Product"
                if st.form_submit_button(submit_label):
                    certs_str = ",".join(certifications)
                    if is_editing and product_to_edit:
                        execute_query(
                            "UPDATE Products SET name=%s, certifications=%s, price=%s, qty=%s, unit=%s, image_url=%s, note=%s WHERE id=%s",
                            (name, certs_str, price, qty, unit, img_url, product_note, product_to_edit.id)
                        )
                        st.session_state.editing_product_id = None
                    else:
                        new_product = Product(name, certs_str, price, qty, unit, st.session_state.email, img_url, product_note)
                        execute_query(
                            "INSERT INTO Products (id, name, certifications, price, qty, unit, producer, image_url, note) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (new_product.id, new_product.name, certs_str, new_product.price, new_product.qty, new_product.unit, new_product.producer, new_product.image_url, new_product.note)
                        )
                    st.rerun()

        with tabs[1]:
            st.subheader("Your Live Listings")
            for idx, p in enumerate(my_products):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 3, 1.5])
                    with c1: st.image(p.image_url, use_container_width=True)
                    with c2:
                        st.write(f"**{p.name}**")
                        st.write(f"Stock: {p.qty} {p.unit} | Price: ${p.price}")
                        with st.expander("Preview Description"):
                            st.markdown(f'<div class="preserve-lines">{p.note}</div>', unsafe_allow_html=True)
                    with c3:
                        if st.button("✏️ Edit Details", key=f"ed_{p.id}"):
                            st.session_state.editing_product_id = p.id
                            st.rerun()
                        if st.button("🗑️ Delete Listing", key=f"del_{p.id}"):
                            execute_query("DELETE FROM Products WHERE id=%s", (p.id,))
                            st.rerun()

        with tabs[2]:
            st.subheader("Detailed Sales & Review History")
            my_sales = [Order(**o) for o in my_orders_data]
            
            if not my_sales:
                st.info("You haven't made any sales yet.")
            else:
                for sale in reversed(my_sales): 
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"#### 📦 {sale.product_name}")
                            st.write(f"**Buyer:** {sale.buyer}")
                            st.write(f"**Quantity:** {sale.qty} {sale.unit} | **Total:** ${sale.total:.2f}")
                        with col2:
                            st.caption(f"📅 {sale.timestamp}")
                        
                        if sale.rating > 0:
                            with st.expander("⭐ View Buyer Review"):
                                st.write(f"**Rating:** {'⭐' * sale.rating} ({sale.rating}/5)")
                                if sale.review:
                                    st.info(f"💬 Feedback: {sale.review}")
                                else:
                                    st.write("*No written comment provided.*")
                        else:
                            st.write("⏳ *Waiting for buyer review...*")
        
        with tabs[3]:
            self.render_messaging_center()

        with tabs[4]:
            st.subheader("🤖 Ceylon Export Assistant")
            if "ai_chat_history" not in st.session_state:
                st.session_state.ai_chat_history = []
            chat_box = st.container(height=400)
            for chat in st.session_state.ai_chat_history:
                with chat_box.chat_message(chat["role"]):
                    st.write(chat["content"])
            if prompt := st.chat_input("Ex: What are the registration steps?"):
                st.session_state.ai_chat_history.append({"role": "user", "content": prompt})
                response = self.assistant.get_response(prompt)
                st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
                st.rerun()

    def render_product_detail_view(self, p):
        st.markdown(f"# {p.name}")
        if st.button("⬅️ Back to Marketplace"):
            st.session_state.selected_product = None
            st.rerun()

        st.divider()
        col_img, col_info = st.columns([1, 1])
        with col_img: st.image(p.image_url, use_container_width=True)
        with col_info:
            with st.container(border=True):
                st.markdown(f"### 💰 Price: ${p.price} / {p.unit}")
                st.write(f"**📍 Producer:** {p.producer}")
                st.write(f"**📦 Stock Available:** {p.qty} {p.unit}")
                
                if p.qty > 0:
                    buy_qty = st.number_input("Enter Order Quantity", 1, max(1, p.qty), key=f"bq_{p.id}")
                    if st.button("⚡ Buy Now", use_container_width=True):
                        new_order = Order(p.id, p.name, buy_qty, p.unit, buy_qty*p.price, st.session_state.email, p.producer)
                        execute_query(
                            "INSERT INTO Orders (id, product_id, product_name, qty, unit, total, buyer, producer, timestamp, rating, review) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (new_order.id, new_order.product_id, new_order.product_name, new_order.qty, new_order.unit, new_order.total, new_order.buyer, new_order.producer, new_order.timestamp, new_order.rating, new_order.review)
                        )
                        execute_query("UPDATE Products SET qty = qty - %s WHERE id = %s", (buy_qty, p.id))
                        st.success("Order Placed Successfully!")
                        st.session_state.selected_product = None
                        st.rerun()
                else:
                    st.error("Out of Stock")

                if st.button("💬 Contact Producer", use_container_width=True):
                    initial_msg = Message(st.session_state.email, p.producer, p.name, f"Hi, I'm interested in your {p.name}.")
                    execute_query("INSERT INTO Messages (sender, receiver, product_name, text, timestamp) VALUES (%s, %s, %s, %s, %s)", 
                                  (initial_msg.sender, initial_msg.receiver, initial_msg.product_name, initial_msg.text, initial_msg.timestamp))
                    st.session_state.active_thread = (p.producer, p.name)
                    st.success("Chat started! Go to Messages tab.")

        st.divider()
        tab_specs, tab_reviews = st.tabs(["📋 Specifications & Description", "⭐ Reviews"])
        with tab_specs:
            st.subheader("📋 Certifications")
            if p.certifications:
                for cert in p.certifications: st.markdown(f"* ✅ {cert}")
            
            st.subheader("📝 Description")
            if p.note:
                st.markdown(f'<div class="preserve-lines">{p.note}</div>', unsafe_allow_html=True)
            else:
                st.write("No description available.")

        with tab_reviews:
            reviews_data = execute_query("SELECT * FROM Orders WHERE product_name=%s AND producer=%s AND rating > 0", (p.name, p.producer), fetch=True)
            if not reviews_data: st.info("No reviews yet for this producer's product.")
            for rev_dict in reviews_data:
                rev = Order(**rev_dict)
                with st.container(border=True):
                    st.write(f"**{rev.buyer}** rated it {'⭐' * rev.rating}")
                    if rev.review: st.write(f"💬 {rev.review}")

    def trader_dashboard(self):
        self.apply_ui_theme()
        if st.session_state.get('selected_product'):
            self.render_product_detail_view(st.session_state.selected_product)
            return

        st.title("🛒 Trade Center")
        tab1, tab2, tab3 = st.tabs(["Marketplace", "My Orders", "💬 Messages"])
        
        with tab1:
            search = st.text_input("🔍 Search products (e.g., Tea, Cinnamon, Gems)...").lower()
            all_products_data = execute_query("SELECT * FROM Products", fetch=True)
            all_products = [Product(**p) for p in all_products_data]
            filtered = [p for p in all_products if search in p.name.lower()]
            
            if not filtered:
                st.warning("No products found matching your search.")
            else:
                cols = st.columns(2)
                for idx, p in enumerate(filtered):
                    with cols[idx % 2]:
                        with st.container(border=True):
                            st.image(p.image_url, use_container_width=True)
                            st.subheader(p.name)
                            st.write(f"Price: ${p.price}/{p.unit}")
                            st.caption(f"Seller: {p.producer}")
                            
                            product_orders = execute_query("SELECT rating FROM Orders WHERE product_name=%s AND producer=%s AND rating > 0", (p.name, p.producer), fetch=True)
                            if product_orders:
                                avg = sum(o['rating'] for o in product_orders) / len(product_orders)
                                st.write(f"{'⭐' * int(avg)} ({avg:.1f})")
                            
                            if st.button("🔎 View Details", key=f"v_{p.id}", use_container_width=True):
                                st.session_state.selected_product = p
                                st.rerun()
        
        with tab2:
            st.subheader("Manage Your Purchases")
            my_orders_data = execute_query("SELECT * FROM Orders WHERE buyer=%s", (st.session_state.email,), fetch=True)
            my_orders = [Order(**o) for o in my_orders_data]

            if not my_orders:
                st.info("You haven't placed any orders yet.")
            
            for o in reversed(my_orders):
                with st.container(border=True):
                    col_txt, col_act = st.columns([3, 1])
                    with col_txt:
                        st.markdown(f"#### **{o.product_name}**")
                        st.write(f"Producer: {o.producer}")
                        st.write(f"Total: **${o.total:.2f}** | Qty: {o.qty} {o.unit}")
                        st.caption(f"Ordered on: {o.timestamp}")
                    
                    with col_act:
                        if st.button("❌ Cancel", key=f"can_{o.id}", use_container_width=True):
                            execute_query("DELETE FROM Orders WHERE id=%s", (o.id,))
                            execute_query("UPDATE Products SET qty = qty + %s WHERE id=%s", (o.qty, o.product_id))
                            st.toast(f"Order for {o.product_name} cancelled.")
                            st.rerun()

                    if o.rating == 0:
                        st.divider()
                        with st.popover(f"⭐ Leave a Review for {o.producer}", use_container_width=True):
                            star = st.select_slider("Rate your experience", options=[1, 2, 3, 4, 5], value=5, key=f"star_{o.id}")
                            rev_text = st.text_area("Write your feedback...", key=f"revtext_{o.id}")
                            if st.button("Submit Feedback", key=f"subrev_{o.id}", use_container_width=True):
                                execute_query("UPDATE Orders SET rating=%s, review=%s WHERE id=%s", (star, rev_text, o.id))
                                st.success("Feedback submitted!")
                                st.rerun()
                    else:
                        st.markdown(f"**Your Rating:** {'⭐' * o.rating}")
                        if o.review:
                            st.caption(f"💬 {o.review}")

        with tab3:
            self.render_messaging_center()

# -----------------------------
# 3. APP STATE INITIALIZATION
# -----------------------------
for key in ["logged_in", "page", "selected_product", "editing_product_id"]:
    if key not in st.session_state:
        if key == "logged_in": st.session_state[key] = False
        elif key == "page": st.session_state[key] = "landing"
        else: st.session_state[key] = None

app = Dashboard()
if st.session_state.page == "landing": app.landing_page()
elif not st.session_state.logged_in:
    if st.session_state.page == "register": app.register_page()
    else: app.login_page()
else:
    st.sidebar.title("Ceylon Trade")
    st.sidebar.info(f"User: {st.session_state.email}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.page = "landing"
        st.session_state.selected_product = None
        st.rerun()
    
    if st.session_state.role == "Producer": app.producer_dashboard()
    else: app.trader_dashboard()