from flask import g, request, jsonify

def register_driver_support(app, db, roles, body, field):
    def conversation(conn, conversation_id):
        row=conn.execute('SELECT * FROM driver_support_conversations WHERE id=%s',(conversation_id,)).fetchone()
        if not row or (g.user['role']=='driver' and row['driver_user_id']!=g.user['id']):
            return None
        return row

    @app.get('/api/driver-support/conversations')
    @roles('admin','driver')
    def driver_support_conversations():
        role=g.user['role'];column='admin_read_id' if role=='admin' else 'driver_read_id'
        where='' if role=='admin' else ' WHERE c.driver_user_id=%s'
        with db() as conn:
            rows=conn.execute('''SELECT c.id,p.name,u.username,m.content AS last_message,m.created_at,
                (SELECT count(*) FROM driver_support_messages sm JOIN users su ON su.id=sm.sender_id
                 WHERE sm.conversation_id=c.id AND sm.id>c.'''+column+''' AND su.role<>%s) AS unread
                FROM driver_support_conversations c JOIN users u ON u.id=c.driver_user_id
                JOIN drivers p ON p.id=u.driver_id
                LEFT JOIN LATERAL (SELECT content,created_at FROM driver_support_messages WHERE conversation_id=c.id
                  ORDER BY id DESC LIMIT 1) m ON true'''+where+' ORDER BY m.created_at DESC NULLS LAST,c.id DESC',
                (role,) if role=='admin' else (role,g.user['id'])).fetchall()
        return jsonify(rows)

    @app.get('/api/driver-support/conversations/<int:conversation_id>/messages')
    @roles('admin','driver')
    def driver_support_messages(conversation_id):
        with db() as conn:
            if not conversation(conn,conversation_id):return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            rows=conn.execute('''SELECT m.id,m.content,m.created_at,u.role AS sender_role,
                COALESCE(a.name,p.name,u.username) AS sender_name
                FROM driver_support_messages m JOIN users u ON u.id=m.sender_id
                LEFT JOIN admin_profiles a ON a.user_id=u.id LEFT JOIN drivers p ON p.id=u.driver_id
                WHERE m.conversation_id=%s ORDER BY m.id DESC LIMIT 100''',(conversation_id,)).fetchall()
        return jsonify(list(reversed(rows)))

    @app.post('/api/driver-support/messages')
    @roles('admin','driver')
    def driver_support_send():
        data=body();content=field(data,'content',2000)
        with db() as conn:
            if g.user['role']=='driver':
                row=conn.execute('''INSERT INTO driver_support_conversations(driver_user_id) VALUES (%s)
                    ON CONFLICT(driver_user_id) DO UPDATE SET driver_user_id=excluded.driver_user_id
                    RETURNING id''',(g.user['id'],)).fetchone()
                conversation_id=row['id']
            else:
                conversation_id=int(data.get('conversation_id',0))
                if not conversation(conn,conversation_id):return jsonify(error='Chọn tài xế để trả lời'),404
            row=conn.execute('''INSERT INTO driver_support_messages(conversation_id,sender_id,content)
                VALUES (%s,%s,%s) RETURNING id,conversation_id''',(conversation_id,g.user['id'],content)).fetchone()
        return jsonify(row),201

    @app.post('/api/driver-support/conversations/<int:conversation_id>/read')
    @roles('admin','driver')
    def driver_support_read(conversation_id):
        last_id=int(body().get('last_id',0))
        with db() as conn:
            if not conversation(conn,conversation_id):return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            row=conn.execute('SELECT id FROM driver_support_messages WHERE conversation_id=%s AND id=%s',(conversation_id,last_id)).fetchone()
            if row:
                column='admin_read_id' if g.user['role']=='admin' else 'driver_read_id'
                conn.execute('UPDATE driver_support_conversations SET '+column+'=GREATEST('+column+',%s) WHERE id=%s',(last_id,conversation_id))
        return jsonify(status='ok')
