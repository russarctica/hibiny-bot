import yookassa
import config
import uuid

# Настройка YooKassa
yookassa.Configuration.account_id = config.YOOKASSA_SHOP_ID
yookassa.Configuration.secret_key = config.YOOKASSA_SECRET_KEY


def create_yookassa_payment(amount: float, description: str, order_id: str, user_id: int) -> str:
    """
    Создаёт платёж в YooKassa и возвращает ссылку для оплаты.
    """
    try:
        payment = yookassa.Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "order_id": order_id,
                "user_id": str(user_id)
            },
            "receipt": {
                "customer": {
                    "email": "user@example.com"
                },
                "items": [
                    {
                        "description": description[:50],
                        "quantity": 1,
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 6,
                        "payment_subject": "service",  # Добавляем обязательный параметр
                        "payment_mode": "full_payment"  # Добавляем обязательный параметр
                    }
                ]
            }
        }, str(uuid.uuid4()))
        
        return payment.confirmation.confirmation_url
    
    except Exception as e:
        print(f"❌ Ошибка создания платежа YooKassa: {e}")
        return None