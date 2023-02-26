# SUT-VK-bot
Бот создан для группы коворкинга СПбГУТ. Позволяет регистрироваться пользователям, записываться в коворкинг, отменять запись. Записываться на лекции в лекторий, а также регистрировать свои мероприятия. Заявки мероприятий от пользователей обязательно подтверждаются администратором.

*Для запуска бота необходимо подготовить:*
- скачать библиотеки vkbottle, pymysql;
- передать боту [токен для использования ВКонтакте](https://faq.botmechanic.io/vk-token) (обязательно включить Long Poll API) - поместить в 12 строку кода бота;
- в настройках группы включить сообщения для бота (управление -> сообщения -> настройки для бота (все включить);
- строки 116 - 120 указать данные для подключения к БД.

Для установки таблицы прикрепляется схема БД:

CREATE TABLE coworking (
  id int NOT NULL AUTO_INCREMENT,
  date varchar(45) NOT NULL,
  students varchar(1000) DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE lections (
  id int NOT NULL AUTO_INCREMENT,
  vk_id varchar(45) DEFAULT NULL,
  date varchar(45) DEFAULT NULL,
  name varchar(45) DEFAULT NULL,
  description varchar(1000) DEFAULT NULL,
  students varchar(1000) DEFAULT NULL,
  isApproved tinyint DEFAULT '0',
  PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE user (
  surname varchar(45) NOT NULL,
  name varchar(45) NOT NULL,
  patrynomic varchar(45) NOT NULL,
  group varchar(45) DEFAULT NULL,
  vk_id varchar(45) DEFAULT NULL,
  is_admin tinyint DEFAULT '0',
  black_list tinyint DEFAULT '0',
  PRIMARY KEY (surname,name,patrynomic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
