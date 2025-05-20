-- Вывод результатов работы хранимых процедур и триггера

-- 1. Вывод среднего рейтинга для всех мероприятий
SELECT 
    e.event_id,
    e.title,
    e.date,
    e.status,
    COALESCE(r.avg_rating, 0) as average_rating,
    COALESCE(r.total_reviews, 0) as total_reviews
FROM Events e
LEFT JOIN (
    SELECT 
        event_id,
        AVG(rating) as avg_rating,
        COUNT(*) as total_reviews
    FROM Reviews
    GROUP BY event_id
) r ON e.event_id = r.event_id
ORDER BY e.event_id;

-- 2. Вывод статусов регистраций и платежей
SELECT 
    r.registration_id,
    e.title as event_title,
    u.username,
    r.role,
    r.status as registration_status,
    p.status as payment_status,
    p.amount
FROM Registrations r
JOIN Events e ON r.event_id = e.event_id
JOIN Users u ON r.user_id = u.user_id
LEFT JOIN Payments p ON r.registration_id = p.registration_id
ORDER BY r.registration_id;

-- 3. Проверка работы триггера (статусы мероприятий)
SELECT 
    event_id,
    title,
    date,
    status,
    CASE 
        WHEN date < CURRENT_TIMESTAMP AND status != 'отменено' THEN 'должен быть завершен'
        ELSE 'статус корректен'
    END as status_check
FROM Events
ORDER BY event_id; 