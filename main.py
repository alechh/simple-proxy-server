import socket
from threading import Thread
import requests


serverSocket = socket.socket()  # создание сокета
localHostIp = "0.0.0.0"  # чтобы работало на всех ip-адресах сервера
port = 1703

# Резервирование порта
serverSocket.bind((localHostIp, port))

# Прослушивание до 10 клиентских подключений
serverSocket.listen(10)

allThreads = set()  # хранение записей всех потоков для присоединения к ним

"""
Без использования буферов данные поступившие от прокси сервера сразу же возвращаются клиенту. 
Если отталкиваеться от того, что клиентское соединение достаточно быстрое, то буферизацию можно отключить. 
При использовании буферов сервер какое-то время хранит ответ полученный от бекэнд сервера и потом отправляет его клиенту 
Если клиент не достаточно быстр, то сервер закрывает соединение с бекэнд-сервером как можно быстрее, 
а данные отправляет клиенту как только тот будет готов их принять. 
"""
buffer = 4096  # Размер буффера


def handle_client_connection(m_client_socket, _m_client_address):
    """
    Метод для получения всех подключений клиента
    """
    client_header = ""
    while True:
        data = m_client_socket.recv(buffer)  # получение запросов от клиента

        try:
            client_header += data.decode("utf-8")
        except UnicodeDecodeError:
            break

        if len(data) < buffer:
            break

    list_header = list(map(str, client_header.strip().split("\r\n")))  # разделение заголовков

    # в зависимости от запроса обрабатываем как http или как https
    if list(map(str, list_header[0].split(" ")))[0].strip() == "GET":
        handle_http_request(m_client_socket, list_header)
    else:
        handle_https_request(m_client_socket, client_header, list_header)


def handle_http_request(m_client_socket, list_header):
    """
    Обработка http запросов
    """
    web_request = requests.get(list(map(str, list_header[0].split(" ")))[1])

    # код ответа об успешном статусе 200 "OK" указывает, что запрос выполнен успешно
    if web_request.status_code == 200:
        response = "HTTP/1.1 200 OK\r\nProxy-Agent: simple-proxy-server\r\n\r\n"
        m_client_socket.send(response.encode("utf-8"))
        m_client_socket.sendall(web_request.text.encode("utf-8"))
    else:
        # страница не найдена
        response = "HTTP/1.1 404 Not Found\r\nProxy-Agent: simple-proxy-server\r\n\r\nYour Website not Found\r\n"
        m_client_socket.send(response.encode("utf-8"))


def handle_https_request(m_client_socket, _client_header, list_header):
    """
    Обработка https запросов
    """
    # AF_INET -- iPv4,
    # SOCK_STREAM -- последовательный, надежный, ориентированный на установление двусторонней связи поток байтов
    web_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        web_host = list(map(str, list_header[0].split(" ")))[1]
        web_host = list(map(str, web_host.split(":")))[0]  # for example: vk.com, habr.com
    except IndexError:
        # Ошибка индекса при получении запроса https
        return

    try:
        web_host_ip = socket.gethostbyname(web_host)
    except socket.gaierror:
        # Ошибка: неправильное имя хоста при получении запроса https
        return

    # если не возникло никаких ошибок
    web_server_socket.connect((web_host_ip, 443))
    response = "HTTP/1.1 200 Connection Established\r\nProxy-Agent: simple-proxy-server\r\n\r\n"
    m_client_socket.send(response.encode("utf-8"))  # 200 Connection Established

    transfer_thread = Thread(target=client_to_server_transfer, args=(m_client_socket, web_server_socket))
    transfer_thread.setDaemon(True)
    transfer_thread.start()  # создание демона

    while True:
        server_data = web_server_socket.recv(buffer)
        m_client_socket.send(server_data)
        if len(server_data) < 1:
            # если пришел запрос на разрыв соединения
            break


def client_to_server_transfer(m_client_socket, web_server_socket):
    """
    Эта функция будет обрабатывать асинхронную передачу данных от клиента к серверу.
    """
    while True:
        client_data = m_client_socket.recv(buffer)
        web_server_socket.send(client_data)
        if len(client_data) < 1:
            # если пришел запрос на разрыв соединения
            break


while True:
    client_socket, client_address = serverSocket.accept()  # установка соединения с клиентом

    # Создание нового потока и обработка клиентского соединения для принятия другого клиентского соединения
    print("Connection accepted from ", client_address)

    thread = Thread(target=handle_client_connection, args=(client_socket, client_address))
    allThreads.add(thread)  # добавление треда в список
    thread.start()
