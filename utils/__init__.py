from database import get_session, User, Setting, Excursion, Expedition, ShopProduct

def load_initial_data(engine):
    """Загрузка начальных данных в базу"""
    session = get_session(engine)
    
    try:
        # Проверяем, есть ли уже данные
        if session.query(Setting).count() == 0:
            # Настройки по умолчанию
            settings = [
                Setting(key='hotel_price', value='10000', description='Цена за ночь в отеле'),
                Setting(key='instructor_formula', value='hours * 2000', description='Формула расчета стоимости инструктора'),
                Setting(key='excursion_base_price', value='2500', description='Базовая цена экскурсии'),
                Setting(key='commission_rate', value='0.1', description='Комиссия 10%'),
                Setting(key='company_phone', value='+7 (911) 123-45-67', description='Телефон компании'),
                Setting(key='company_email', value='booking@hibiny.ru', description='Email компании'),
                Setting(key='manager_telegram', value='@manager_hb', description='Telegram менеджера'),
                Setting(key='whatsapp_number', value='79111234567', description='WhatsApp для уведомлений'),
                Setting(key='sbp_requisites', value='Сбербанк 2202 2001 2345 6789', description='Реквизиты для СБП'),
            ]
            
            for setting in settings:
                session.add(setting)
            
            # Базовые экскурсии
            excursions = [
                Excursion(
                    name='Териберка',
                    description='Путешествие к Баренцеву морю, водопад, берег океана.',
                    base_price=3500,
                    duration='8-10 часов'
                ),
                Excursion(
                    name='Кандалакша (Белое море)',
                    description='Морская прогулка, птичий базар, уникальная природа.',
                    base_price=4000,
                    duration='10-12 часов'
                ),
                Excursion(
                    name='Северное сияние',
                    description='Ночное сафари за северным сиянием с профессиональным гидом.',
                    base_price=3000,
                    duration='4-6 часов'
                ),
                Excursion(
                    name='Снегоходы/Квадроциклы',
                    description='Активный отдых на снегоходах или квадроциклах.',
                    base_price=5000,
                    duration='2-3 часа'
                ),
                Excursion(
                    name='Айсфлоатинг',
                    description='Уникальная процедура в ледяной воде с термальным контрастом.',
                    base_price=4500,
                    duration='3-4 часа'
                ),
                Excursion(
                    name='Хибины',
                    description='Пеший тур по горным тропам Хибин с видами на долины.',
                    base_price=2500,
                    duration='5-6 часов'
                ),
            ]
            
            for excursion in excursions:
                session.add(excursion)
            
            # Экспедиции
            expeditions = [
                Expedition(
                    name='Зимняя экспедиция 2025',
                    season='winter',
                    year=2025,
                    description='Экстремальное путешествие по зимней Арктике с ночевками в ледяных домах.',
                    price=150000
                ),
                Expedition(
                    name='Летняя экспедиция 2025',
                    season='summer',
                    year=2025,
                    description='Исследование летней Арктики, морские прогулки, наблюдение за китами.',
                    price=180000
                ),
            ]
            
            for expedition in expeditions:
                session.add(expedition)
            
            # Товары для магазина
            products = [
                ShopProduct(
                    name='Футболка "Хибины"',
                    description='Хлопковая футболка с принтом Хибин',
                    price=1500,
                    product_type='physical',
                    stock=50
                ),
                ShopProduct(
                    name='Кружка с северным сиянием',
                    description='Керамическая кружка с термоизменяющимся рисунком',
                    price=800,
                    product_type='physical',
                    stock=30
                ),
                ShopProduct(
                    name='Фотогид по Хибинам (PDF)',
                    description='Цифровой гид с фотографиями и описанием маршрутов',
                    price=500,
                    product_type='digital'
                ),
                ShopProduct(
                    name='Карта звездного неба Хибин',
                    description='Интерактивная карта для наблюдения за северным сиянием',
                    price=1200,
                    product_type='digital'
                ),
            ]
            
            for product in products:
                session.add(product)
            
            session.commit()
            print("✅ Начальные данные загружены")
        
    except Exception as e:
        print(f"❌ Ошибка при загрузке данных: {e}")
        session.rollback()
    finally:
        session.close()