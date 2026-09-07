import openai
import config
import re

client = openai.OpenAI(
    api_key=config.YANDEX_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=config.YANDEX_FOLDER_ID,
    timeout=120.0  # Увеличиваем таймаут до 120 секунд
)

def clean_answer(text: str) -> str:
    """
    Убирает служебные фразы в начале ответа (воду).
    """
    if not text:
        return text
    
    # Разбиваем на строки
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        # Пропускаем строки-паразиты
        skip = False
        patterns = [
            r'(?i)^отлично[,\s!]',
            r'(?i)^хорошо[,\s!]',
            r'(?i)^теперь[,\s!]',
            r'(?i)^давайте[,\s!]',
            r'(?i)^я (?:нашёл|получил|изучил)',
            r'(?i)^у меня (?:уже )?достаточно',
            r'(?i)^страница .*? не содержит',
            r'(?i)^давайте также посмотр',
            r'(?i)^теперь мне нужно прочитат',
            r'(?i)^мне нужно найти',
            r'(?i)^эта страница не содержит',
            r'(?i)^я также проверю',
            r'(?i)^чтобы получить более детальную',
            r'(?i)^давайте прочитаю',
            r'^---$',
        ]
        
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                skip = True
                break
        
        if not skip and line.strip():
            # Если это первый непустой полезный заголовок — начинаем сбор
            if not clean_lines and re.match(r'^[#*📍]', line.strip()):
                clean_lines.append(line)
            elif clean_lines:
                clean_lines.append(line)
    
    result = '\n'.join(clean_lines)
    
    # Если результат пустой — возвращаем исходный текст
    if not result.strip():
        return text
    
    return result


def ask_deepseek(user_question: str) -> str:
    """
    Отправляет вопрос в Yandex GPT через агента с интернет-поиском.
    """
    print(f"🔍 ask_deepseek вызван с вопросом: {user_question[:50]}...")
    print(f"🔑 API Key: {config.YANDEX_API_KEY[:10]}...")
    
    try:
        response = client.responses.create(
            prompt={
                "id": "fvta4gn49a34ecdtrhdf",
            },
            input=user_question,
            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": []
                    },
                    "search_context_size": "high",
                    "user_location": {
                        "type": "approximate",
                        "region": "23"
                    }
                }
            ],
            temperature=0.3,
            timeout=120  # Таймаут для конкретного запроса
        )
        
        answer = response.output_text
        
        # ОЧИЩАЕМ ОТВЕТ ОТ ВОДЫ
        answer = clean_answer(answer)
        
        # Обрезаем только если ответ всё ещё слишком длинный
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n📌 *Ответ слишком длинный, я его обрезал.* Если нужно больше деталей — уточните вопрос."
        
        print(f"✅ Ответ получен: {answer[:50]}...")
        return answer

    except Exception as e:
        print(f"❌ Ошибка Yandex GPT: {e}")
        return "😔 *Извините, произошла ошибка.* Попробуйте переформулировать вопрос. Если проблема повторяется — напишите менеджеру."