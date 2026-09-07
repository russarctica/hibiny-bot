import json
from database import get_db, User, UserState
from states import UserStates, StateData

class StateManager:
    """Менеджер состояний пользователей"""
    
    @staticmethod
    def get_state(user_id):
        """Получить текущее состояние пользователя"""
        with next(get_db()) as db:
            state = db.query(UserState).filter_by(user_id=user_id).first()
            if state:
                return UserStates(state.state)
            return UserStates.MAIN_MENU
    
    @staticmethod
    def set_state(user_id, state, data=None):
        """Установить состояние пользователя"""
        with next(get_db()) as db:
            user_state = db.query(UserState).filter_by(user_id=user_id).first()
            
            if not user_state:
                user_state = UserState(
                    user_id=user_id,
                    state=state.value,
                    data=json.dumps(data.to_dict() if isinstance(data, StateData) else (data if isinstance(data, dict) else {}))
                )
                db.add(user_state)
            else:
                # Сохраняем предыдущее состояние
                user_state.previous_state = user_state.state
                user_state.previous_data = user_state.data
                
                # Устанавливаем новое состояние
                user_state.state = state.value
                user_state.data = json.dumps(data.to_dict() if isinstance(data, StateData) else (data if isinstance(data, dict) else {}))
            
            db.commit()
            print(f"📌 State set: user={user_id}, state={state.value}, data={user_state.data[:100] if user_state.data else '{}'}")
    
    @staticmethod
    def get_data(user_id):
        """Получить данные состояния пользователя"""
        with next(get_db()) as db:
            state = db.query(UserState).filter_by(user_id=user_id).first()
            if state and state.data:
                try:
                    data_dict = json.loads(state.data)
                    if hasattr(StateData, 'from_dict'):
                        return StateData.from_dict(data_dict)
                    else:
                        # Если from_dict не существует, создаем StateData из словаря
                        return StateData(**data_dict)
                except Exception as e:
                    print(f"❌ Ошибка загрузки данных: {e}")
                    return StateData()
            return StateData()
    
    @staticmethod
    def update_data(user_id, **kwargs):
        """Обновить данные состояния пользователя"""
        with next(get_db()) as db:
            state = db.query(UserState).filter_by(user_id=user_id).first()
            if state:
                try:
                    data_dict = json.loads(state.data) if state.data else {}
                except:
                    data_dict = {}
                
                data_dict.update(kwargs)
                state.data = json.dumps(data_dict)
                db.commit()
                print(f"📌 Data updated: user={user_id}, updates={kwargs}")
                if hasattr(StateData, 'from_dict'):
                    return StateData.from_dict(data_dict)
                else:
                    return StateData(**data_dict)
            return StateData()
    
    @staticmethod
    def go_back(user_id):
        """Вернуться к предыдущему состоянию"""
        with next(get_db()) as db:
            state = db.query(UserState).filter_by(user_id=user_id).first()
            if state and state.previous_state:
                state.state = state.previous_state
                state.data = state.previous_data
                state.previous_state = None
                state.previous_data = None
                db.commit()
                print(f"📌 Go back: user={user_id}, new state={state.state}")
                return True
            return False
    
    @staticmethod
    def clear_state(user_id):
        """Очистить состояние (вернуться в главное меню)"""
        with next(get_db()) as db:
            state = db.query(UserState).filter_by(user_id=user_id).first()
            if state:
                state.state = UserStates.MAIN_MENU.value
                state.data = '{}'
                state.previous_state = None
                state.previous_data = None
                db.commit()
                print(f"📌 State cleared: user={user_id}")