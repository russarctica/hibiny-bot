import os
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime

# Создаем базовый класс
Base = declarative_base()

# ========== ТАБЛИЦЫ БАЗЫ ДАННЫХ ==========

class User(Base):
    """Пользователи"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    is_admin = Column(Boolean, default=False)
    is_instructor = Column(Boolean, default=False)
    is_guide = Column(Boolean, default=False)
    receive_promo = Column(Boolean, default=True)

    hotel_bookings = relationship("HotelBooking", back_populates="user")
    instructor_bookings = relationship("InstructorBooking", back_populates="user")
    user_states = relationship("UserState", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class HotelBooking(Base):
    """Брони отеля"""
    __tablename__ = 'hotel_bookings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    booking_id = Column(String(50), unique=True)
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime, nullable=False)
    nights = Column(Integer)
    total_price = Column(Float, default=0)
    status = Column(String(50), default='pending')
    payment_status = Column(String(50), default='unpaid')
    name = Column(String(100))
    phone = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="hotel_bookings")
    services = relationship("HotelService", back_populates="booking")

class HotelService(Base):
    """Допуслуги отеля"""
    __tablename__ = 'hotel_services'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('hotel_bookings.id'))
    service_type = Column(String(100))
    description = Column(Text)
    price = Column(Float, default=0)
    status = Column(String(50), default='pending')

    booking = relationship("HotelBooking", back_populates="services")

class InstructorBooking(Base):
    """Заявки на инструкторов"""
    __tablename__ = 'instructor_bookings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    booking_id = Column(String(50), unique=True)
    program = Column(String(100))
    lesson_type = Column(String(50))
    group_size = Column(Integer, default=1)
    student_type = Column(String(50))
    hours = Column(Integer)
    lesson_date = Column(String(20))
    lesson_time = Column(String(10))
    client_name = Column(String(100))
    client_phone = Column(String(20))
    base_price = Column(Float, default=0)
    total_price = Column(Float, default=0)
    instructor_id = Column(Integer, nullable=True)
    instructor_name = Column(String(100), nullable=True)
    commission_percent = Column(Float, default=10)
    commission_amount = Column(Float, default=0)
    status = Column(String(50), default='searching')
    payment_status = Column(String(50), default='unpaid')
    instructors_chat_message_id = Column(Integer, nullable=True)
    offer_expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    reminder_24h_sent = Column(Boolean, default=False)
    reminder_2h_sent = Column(Boolean, default=False)
    reminder_end_sent = Column(Boolean, default=False)
    sport = Column(String(100), nullable=True)
    group_type = Column(String(50), default='individual')
    group_status = Column(String(50), nullable=True)
    children_info = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_rebook = Column(Boolean, default=False)

    user = relationship("User", back_populates="instructor_bookings")
    offers = relationship("InstructorOffer", back_populates="booking")
    extensions = relationship("InstructorExtension", back_populates="booking")

class InstructorOffer(Base):
    """Предложения инструкторов"""
    __tablename__ = 'instructor_offers'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('instructor_bookings.id'))
    instructor_id = Column(Integer)
    instructor_name = Column(String(100))
    instructor_username = Column(String(100))
    instructor_phone = Column(String(20))
    price = Column(Float)
    offer_date = Column(String(20))
    offer_time = Column(String(20))
    message = Column(Text)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.now)

    booking = relationship("InstructorBooking", back_populates="offers")

class InstructorExtension(Base):
    """Продления занятий с инструкторами"""
    __tablename__ = 'instructor_extensions'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('instructor_bookings.id'))
    extension_type = Column(String(50))
    extension_date = Column(String(20), nullable=True)
    extension_hours = Column(Integer)
    additional_price = Column(Float, default=0)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.now)

    booking = relationship("InstructorBooking", back_populates="extensions")

class Excursion(Base):
    """Экскурсии"""
    __tablename__ = 'excursions'

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    price_per_person = Column(Float, default=0)
    min_people = Column(Integer, default=1)
    max_people = Column(Integer, default=10)
    duration_hours = Column(Integer, default=2)
    default_start_time = Column(String(10), default="10:00")
    photo_file_id = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    start_date = Column(String(20), nullable=True)
    end_date = Column(String(20), nullable=True)
    start_location = Column(String(200), nullable=True)
    is_tour = Column(Boolean, default=False)
    prepayment_percent = Column(Integer, default=30)
    cancellation_days = Column(Integer, default=3)
    group_discount = Column(Integer, default=0)
    guide_user_id = Column(Integer, nullable=True)
    access_paid = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)

class ExcursionBooking(Base):
    """Брони экскурсий"""
    __tablename__ = 'excursion_bookings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    excursion_id = Column(Integer, ForeignKey('excursions.id'))
    booking_id = Column(String(50), unique=True)
    booking_date = Column(String(20))
    excursion_time = Column(String(10), default="10:00")
    people_count = Column(Integer)
    client_name = Column(String(100))
    client_phone = Column(String(20))
    total_price = Column(Float, default=0)
    guide_id = Column(Integer, nullable=True)
    guide_name = Column(String(100), nullable=True)
    status = Column(String(50), default='pending')
    payment_status = Column(String(50), default='unpaid')
    reminder_24h_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    has_children = Column(Boolean, default=False)
    children_info = Column(Text, nullable=True)
    group_status = Column(String(50), nullable=True)
    group_members = Column(Text, nullable=True)
    prepayment_amount = Column(Float, default=0)
    prepayment_paid = Column(Boolean, default=False)
    prepayment_paid_at = Column(DateTime, nullable=True)
    guide_start_location = Column(String(200), nullable=True)
    guide_note = Column(Text, nullable=True)
    excursion_start_time = Column(String(10), nullable=True)
    excursion_end_time = Column(String(10), nullable=True)
    is_tour_booking = Column(Boolean, default=False)
    tour_days = Column(Integer, default=0)
    is_rebook = Column(Boolean, default=False)
    is_joining_group = Column(Boolean, default=False)
    client_note = Column(Text, nullable=True)
    is_first_in_group = Column(Boolean, default=False)
    parent_booking_id = Column(Integer, nullable=True)
    group_min_people = Column(Integer, nullable=True)
    group_max_people = Column(Integer, nullable=True)
    group_is_ready = Column(Boolean, default=False)
    group_checked_24h = Column(Boolean, default=False)
    group_checked_2h = Column(Boolean, default=False)
    guide_conditions_set = Column(Boolean, default=False)
    guide_price_per_person = Column(Float, nullable=True)
    client_contacts_hidden = Column(Boolean, default=True)

class ExcursionOffer(Base):
    """Предложения гидов по экскурсиям"""
    __tablename__ = 'excursion_offers'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey('excursion_bookings.id'))
    guide_id = Column(Integer)
    guide_name = Column(String(100))
    guide_username = Column(String(100))
    offer_date = Column(String(20))
    offer_time = Column(String(10))
    description = Column(Text)
    price = Column(Float)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.now)

class Guide(Base):
    """Гиды"""
    __tablename__ = 'guides'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    name = Column(String(100))
    username = Column(String(100))
    phone = Column(String(20))
    specialties = Column(Text)
    rating = Column(Float, default=5.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class Expedition(Base):
    """Экспедиции"""
    __tablename__ = 'expeditions'

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    program = Column(Text)
    included = Column(Text)
    price = Column(Float, default=0)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    max_participants = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class ExpeditionBooking(Base):
    """Заявки на экспедиции"""
    __tablename__ = 'expedition_bookings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    expedition_id = Column(Integer, ForeignKey('expeditions.id'))
    booking_id = Column(String(50), unique=True)
    people_count = Column(Integer)
    client_name = Column(String(100))
    client_phone = Column(String(20))
    wishes = Column(Text, nullable=True)
    status = Column(String(50), default='pending')
    payment_status = Column(String(50), default='unpaid')
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class ShopProduct(Base):
    """Товары магазина"""
    __tablename__ = 'shop_products'

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    price = Column(Float, default=0)
    category = Column(String(100))
    photo_file_id = Column(String(500), nullable=True)
    file_url = Column(String(500), nullable=True)
    stock = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class ShopOrder(Base):
    """Заказы магазина"""
    __tablename__ = 'shop_orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    order_id = Column(String(50), unique=True)
    product_id = Column(Integer, ForeignKey('shop_products.id'))
    quantity = Column(Integer, default=1)
    total_price = Column(Float, default=0)
    delivery_address = Column(Text, nullable=True)
    tracking_number = Column(String(100), nullable=True)
    status = Column(String(50), default='pending')
    payment_status = Column(String(50), default='unpaid')
    created_at = Column(DateTime, default=datetime.now)

    product = relationship("ShopProduct")

class Payment(Base):
    """Платежи"""
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    booking_type = Column(String(50))
    booking_id = Column(Integer)
    amount = Column(Float)
    commission = Column(Float, default=0)
    payment_method = Column(String(50))
    status = Column(String(50), default='pending')
    transaction_id = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="payments")

class Setting(Base):
    """Настройки"""
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class BlockedDate(Base):
    """Занятые/заблокированные даты отеля"""
    __tablename__ = 'blocked_dates'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True)
    reason = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)

class UserState(Base):
    """Состояния пользователей для кнопки 'Назад'"""
    __tablename__ = 'user_states'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    state = Column(String(100))
    data = Column(Text)
    previous_state = Column(String(100))
    previous_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="user_states")

class PromoOffer(Base):
    """Промо-предложения для рассылки"""
    __tablename__ = 'promo_offers'

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    price = Column(Float, default=0)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(Integer)

class BroadcastMessage(Base):
    """Рассылки сообщений"""
    __tablename__ = 'broadcast_messages'

    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    message = Column(Text)
    message_type = Column(String(50))
    file_id = Column(String(500), nullable=True)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    status = Column(String(50), default='draft')
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(Integer)

class DailyReport(Base):
    """Ежедневные отчеты"""
    __tablename__ = 'daily_reports'

    id = Column(Integer, primary_key=True)
    report_date = Column(DateTime, unique=True)
    hotel_bookings = Column(Integer, default=0)
    hotel_revenue = Column(Float, default=0)
    instructor_bookings = Column(Integer, default=0)
    instructor_revenue = Column(Float, default=0)
    excursion_bookings = Column(Integer, default=0)
    excursion_revenue = Column(Float, default=0)
    shop_orders = Column(Integer, default=0)
    shop_revenue = Column(Float, default=0)
    total_revenue = Column(Float, default=0)
    new_users = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    report_text = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========

def init_db():
    """Инициализация базы данных"""
    os.makedirs('data', exist_ok=True)
    engine = create_engine(f'sqlite:///data/database.db', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    default_settings = [
        {'key': 'hotel_price_per_night', 'value': '10000'},
        {'key': 'instructor_base_price', 'value': '2000'},
        {'key': 'instructor_group_discount', 'value': '10'},
        {'key': 'instructor_child_price', 'value': '1500'},
        {'key': 'instructor_freeride_price', 'value': '2500'},
        {'key': 'instructor_carving_price', 'value': '2500'},
        {'key': 'instructor_commission', 'value': '10'},
        {'key': 'guide_commission', 'value': '10'},
        {'key': 'sbp_bank_account', 'value': '40817810099910004312'},
        {'key': 'sbp_bank_name', 'value': 'Сбербанк'},
        {'key': 'sbp_bic', 'value': '044525225'},
        {'key': 'manager_chat_id', 'value': ''},
        {'key': 'instructors_chat_id', 'value': ''},
        {'key': 'guides_chat_id', 'value': ''},
        {'key': 'offer_expiration_hours', 'value': '48'},
        {'key': 'excursion_commission', 'value': '10'},
        {'key': 'daily_report_time', 'value': '23:59'},
        {'key': 'weekly_report_day', 'value': 'sunday'},
        {'key': 'monthly_report_day', 'value': '1'},
        {'key': 'group_slots_interval_days', 'value': '2'},
        {'key': 'group_slots_times', 'value': '["12:00-14:00", "15:00-17:00"]'},
    ]

    for setting in default_settings:
        if not session.query(Setting).filter_by(key=setting['key']).first():
            new_setting = Setting(key=setting['key'], value=setting['value'])
            session.add(new_setting)

    if not session.query(Excursion).first():
        test_excursions = [
            Excursion(
                name='Териберка',
                description='Путешествие к побережью Баренцева моря с посещением старинного поморского села Териберка. Вы увидите знаменитый водопад, каменный пляж "Яйца дракона", кладбище деревянных кораблей. По пути — тундра, сопки и захватывающие дух виды. Экскурсия занимает весь день, около 8 часов. Рекомендуем взять тёплую одежду, удобную обувь, фотоаппарат и перекус.',
                price_per_person=5000,
                min_people=2,
                max_people=8,
                duration_hours=8,
                default_start_time="10:00"
            ),
            Excursion(
                name='Кандалакша',
                description='Поездка в Кандалакшу — город на берегу Белого моря. Вы посетите Кандалакшский залив, каменные лабиринты, сейды, Крестовую гору. Экскурсия длится около 7 часов. Рекомендуем одеться по погоде, взять с собой еду, воду, фотоаппарат и хорошее настроение.',
                price_per_person=4500,
                min_people=2,
                max_people=6,
                duration_hours=7,
                default_start_time="10:00"
            ),
            Excursion(
                name='Айс-флоатинг',
                description='Уникальный опыт плавания в ледяной воде в специальном защитном гидрокостюме. Вы будете дрейфовать среди льдин в озере или море, чувствуя полную невесомость. Экскурсия длится около 3 часов. Всё снаряжение предоставляется. Рекомендуем взять тёплую одежду под костюм, шапку, перчатки, сменные носки и термос с горячим чаем.',
                price_per_person=3500,
                min_people=2,
                max_people=8,
                duration_hours=3,
                default_start_time="12:00"
            ),
            Excursion(
                name='Северное сияние',
                description='Ночная вылазка за город для наблюдения за одним из самых захватывающих природных явлений — северным сиянием. Гид-фотограф поможет вам найти лучшую локацию и сделать потрясающие снимки. Экскурсия длится около 4 часов, начинается вечером. Рекомендуем одеться очень тепло, взять термос с горячим напитком, запасные аккумуляторы для техники и штатив для фотоаппарата.',
                price_per_person=3000,
                min_people=1,
                max_people=10,
                duration_hours=4,
                default_start_time="21:00"
            ),
        ]
        for excursion in test_excursions:
            session.add(excursion)

        test_tours = [
            Excursion(
                name='Мурманский тур на 3 дня',
                description='Трёхдневное путешествие по Кольскому полуострову с посещением Териберки и Кандалакши.',
                price_per_person=25000,
                min_people=2,
                max_people=6,
                duration_hours=72,
                start_date='20.07.2026',
                end_date='22.07.2026',
                start_location='Мурманск',
                is_tour=True,
                is_published=True
            ),
            Excursion(
                name='Хибинский тур на 5 дней',
                description='Пятидневный поход по Хибинским горам с восхождением на вершины.',
                price_per_person=45000,
                min_people=2,
                max_people=8,
                duration_hours=120,
                start_date='01.08.2026',
                end_date='05.08.2026',
                start_location='Кировск',
                is_tour=True,
                is_published=True
            ),
            Excursion(
                name='Кольский тур на 4 дня',
                description='Четырёхдневное путешествие по Кольскому полуострову.',
                price_per_person=35000,
                min_people=2,
                max_people=6,
                duration_hours=96,
                start_date='15.08.2026',
                end_date='18.08.2026',
                start_location='Апатиты',
                is_tour=True,
                is_published=True
            ),
        ]
        for tour in test_tours:
            session.add(tour)

    if not session.query(ShopProduct).first():
        test_products = [
            ShopProduct(
                name='Гид по Хибинам (PDF)',
                description='Полный гид по маршрутам Хибинских гор с картами и описаниями.',
                price=500,
                category='digital',
                stock=999
            ),
            ShopProduct(
                name='Футболка "Хибины"',
                description='Хлопковая футболка с принтом Хибинских гор.',
                price=1500,
                category='physical',
                stock=50
            ),
            ShopProduct(
                name='Термос 1л',
                description='Термос для горячих напитков в походе.',
                price=1200,
                category='physical',
                stock=30
            ),
        ]
        for product in test_products:
            session.add(product)

    if not session.query(Expedition).first():
        test_expeditions = [
            Expedition(
                name='Зимняя экспедиция 2025',
                description='Экспедиция по зимним Хибинам с ночевкой в горной хижине.',
                program='1 день: Встреча в Кировске, переход к хижине.\n2 день: Восхождение на вершину, фотографирование.\n3 день: Возвращение в Кировск.',
                included='Проживание, питание, снаряжение, услуги гида',
                price=15000,
                start_date=datetime(2025, 2, 15),
                end_date=datetime(2025, 2, 17),
                max_participants=8
            ),
            Expedition(
                name='Летняя экспедиция 2025',
                description='Летний поход по горным тропам Хибин.',
                program='1 день: Встреча в Апатитах, переход к лагерю.\n2 день: Радиальные выходы, фотографирование.\n3 день: Возвращение в Апатиты.',
                included='Проживание в палатках, питание, снаряжение, услуги гида',
                price=12000,
                start_date=datetime(2025, 7, 10),
                end_date=datetime(2025, 7, 12),
                max_participants=10
            ),
        ]
        for expedition in test_expeditions:
            session.add(expedition)

    session.commit()
    session.close()

    print("✅ База данных успешно инициализирована!")
    return engine

engine = init_db()
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == '__main__':
    print("Создание базы данных...")