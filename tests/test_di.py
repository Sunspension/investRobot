#!/usr/bin/env python3
"""
Тесты для системы управления зависимостями (DI)
"""
import unittest
from unittest.mock import Mock, MagicMock
from robotlib.di.service_locator import ServiceLocator, get_service_locator
from robotlib.di.interfaces import Factoryable, ServiceLocatable


class MockService:
    """Мок-сервис для тестирования"""
    def __init__(self, value: str = "default"):
        self.value = value


class MockFactory(Factoryable):
    """Мок-фабрика для тестирования"""
    
    def __init__(self, return_value: MockService = None):
        self.return_value = return_value or MockService("factory_created")
        self.create_called = False
        self.create_args = None
        self.create_kwargs = None
    
    def create(self, *args, **kwargs) -> MockService:
        """Создает экземпляр MockService"""
        self.create_called = True
        self.create_args = args
        self.create_kwargs = kwargs
        return self.return_value


class TestFactoryable(unittest.TestCase):
    """Тесты для интерфейса Factoryable"""
    
    def test_factory_interface(self):
        """Тест что MockFactory реализует интерфейс Factoryable"""
        factory = MockFactory()
        self.assertIsInstance(factory, Factoryable)
    
    def test_factory_create(self):
        """Тест создания через фабрику"""
        factory = MockFactory()
        result = factory.create("test_arg", test_kwarg="test_value")
        
        self.assertIsInstance(result, MockService)
        self.assertEqual(result.value, "factory_created")
        self.assertTrue(factory.create_called)
        self.assertEqual(factory.create_args, ("test_arg",))
        self.assertEqual(factory.create_kwargs, {"test_kwarg": "test_value"})


class TestServiceLocator(unittest.TestCase):
    """Тесты для ServiceLocator"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.service_locator = ServiceLocator()
    
    def test_initialization(self):
        """Тест инициализации сервис-локатора"""
        self.assertIsNotNone(self.service_locator)
        self.assertEqual(len(self.service_locator._factories), 0)
        self.assertEqual(len(self.service_locator._instances), 0)
    
    def test_register_factory(self):
        """Тест регистрации фабрики"""
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        
        self.assertTrue(self.service_locator.is_registered(MockService))
        self.assertIn(MockService, self.service_locator._factories)
        self.assertEqual(self.service_locator._factories[MockService], factory)
    
    def test_register_instance(self):
        """Тест регистрации готового экземпляра"""
        instance = MockService("registered_instance")
        self.service_locator.register_instance(MockService, instance)
        
        self.assertTrue(self.service_locator.is_registered(MockService))
        self.assertIn(MockService, self.service_locator._instances)
        self.assertEqual(self.service_locator._instances[MockService], instance)
    
    def test_get_from_factory(self):
        """Тест получения сервиса через фабрику"""
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        
        result = self.service_locator.get(MockService)
        
        self.assertIsInstance(result, MockService)
        self.assertEqual(result.value, "factory_created")
        self.assertTrue(factory.create_called)
    
    def test_get_from_instance(self):
        """Тест получения готового экземпляра"""
        instance = MockService("registered_instance")
        self.service_locator.register_instance(MockService, instance)
        
        result = self.service_locator.get(MockService)
        
        self.assertIs(result, instance)
        self.assertEqual(result.value, "registered_instance")
    
    def test_get_instance_priority_over_factory(self):
        """Тест что готовый экземпляр имеет приоритет над фабрикой"""
        factory = MockFactory()
        instance = MockService("registered_instance")
        
        self.service_locator.register(MockService, factory)
        self.service_locator.register_instance(MockService, instance)
        
        result = self.service_locator.get(MockService)
        
        self.assertIs(result, instance)
        self.assertEqual(result.value, "registered_instance")
        self.assertFalse(factory.create_called)
    
    def test_get_unregistered_service(self):
        """Тест получения незарегистрированного сервиса"""
        with self.assertRaises(RuntimeError) as context:
            self.service_locator.get(MockService)
        
        self.assertIn("Сервис MockService не зарегистрирован", str(context.exception))
    
    def test_get_factory(self):
        """Тест получения фабрики"""
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        
        result = self.service_locator.get_factory(MockService)
        
        self.assertIs(result, factory)
    
    def test_get_unregistered_factory(self):
        """Тест получения незарегистрированной фабрики"""
        with self.assertRaises(RuntimeError) as context:
            self.service_locator.get_factory(MockService)
        
        self.assertIn("Фабрика для MockService не зарегистрирована", str(context.exception))
    
    def test_is_registered(self):
        """Тест проверки регистрации сервиса"""
        self.assertFalse(self.service_locator.is_registered(MockService))
        
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        self.assertTrue(self.service_locator.is_registered(MockService))
        
        self.service_locator._factories.clear()
        instance = MockService()
        self.service_locator.register_instance(MockService, instance)
        self.assertTrue(self.service_locator.is_registered(MockService))
    
    def test_list_services(self):
        """Тест получения списка сервисов"""
        # Пустой список
        services = self.service_locator.list_services()
        self.assertEqual(len(services), 0)
        
        # Добавляем фабрику
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        services = self.service_locator.list_services()
        self.assertIn("MockService", services)
        self.assertIn("Factory: MockFactory", services["MockService"])
        
        # Добавляем экземпляр
        instance = MockService()
        self.service_locator.register_instance(str, instance)
        services = self.service_locator.list_services()
        self.assertIn("str", services)
        self.assertIn("Instance: MockService", services["str"])
    
    def test_clear(self):
        """Тест очистки сервис-локатора"""
        factory = MockFactory()
        instance = MockService()
        
        self.service_locator.register(MockService, factory)
        self.service_locator.register_instance(str, instance)
        
        self.assertTrue(self.service_locator.is_registered(MockService))
        self.assertTrue(self.service_locator.is_registered(str))
        
        self.service_locator.clear()
        
        self.assertFalse(self.service_locator.is_registered(MockService))
        self.assertFalse(self.service_locator.is_registered(str))
        self.assertEqual(len(self.service_locator._factories), 0)
        self.assertEqual(len(self.service_locator._instances), 0)
    
    def test_factory_with_arguments(self):
        """Тест создания через фабрику с аргументами"""
        factory = MockFactory()
        self.service_locator.register(MockService, factory)
        
        result = self.service_locator.get(MockService)
        
        # Проверяем что фабрика была вызвана без аргументов
        self.assertTrue(factory.create_called)
        self.assertEqual(factory.create_args, ())
        self.assertEqual(factory.create_kwargs, {})


class TestServiceLocatorSingleton(unittest.TestCase):
    """Тесты для глобального экземпляра сервис-локатора"""
    
    def test_get_service_locator_singleton(self):
        """Тест что get_service_locator возвращает один и тот же экземпляр"""
        locator1 = get_service_locator()
        locator2 = get_service_locator()
        
        self.assertIs(locator1, locator2)
        self.assertIsInstance(locator1, ServiceLocator)
    
    def test_singleton_persistence(self):
        """Тест что данные сохраняются в глобальном экземпляре"""
        locator = get_service_locator()
        factory = MockFactory()
        
        locator.register(MockService, factory)
        
        # Получаем тот же экземпляр и проверяем что данные сохранились
        same_locator = get_service_locator()
        self.assertTrue(same_locator.is_registered(MockService))
        
        result = same_locator.get(MockService)
        self.assertIsInstance(result, MockService)


class TestServiceLocatorInterface(unittest.TestCase):
    """Тесты совместимости с интерфейсом ServiceLocatable"""
    
    def test_service_locator_implements_interface(self):
        """Тест что ServiceLocator реализует интерфейс ServiceLocatable"""
        service_locator = ServiceLocator()
        self.assertIsInstance(service_locator, ServiceLocatable)
    
    def test_interface_methods(self):
        """Тест что все методы интерфейса реализованы"""
        service_locator = ServiceLocator()
        factory = MockFactory()
        
        # register
        service_locator.register(MockService, factory)
        
        # get
        result = service_locator.get(MockService)
        self.assertIsInstance(result, MockService)
        
        # get_factory
        retrieved_factory = service_locator.get_factory(MockService)
        self.assertIs(retrieved_factory, factory)


if __name__ == '__main__':
    unittest.main()


