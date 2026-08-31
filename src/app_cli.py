from src.agents.lead import LeadAgent
from loguru import logger

lead_agent = LeadAgent()

def run():
    print(
        "Mentor Bahasa Inggris Virtual\n"
        "Coba tulis pesan: \n"
        "- buatkan soal reading \n"
        "- periksa: I goes to school \n"
        "- berikan saya tips belajar \n"
        "atau ngobrol bebas"
    )
    
    while True:
        prompt = input("[user]: ")
        
        if prompt.lower() == "/exit":
            break
        
        response = lead_agent.handle_send_message(user_id="", message_text=prompt)
        
        logger.success(f"[AI]: {response.text}")