from flask import g, request, jsonify

def register_support(app, db, roles, body, field):
    def conversation(conn, conversation_id):
        row=conn.execute('SELECT * FROM support_conversations WHERE id=%s',(conversation_id,)).fetchone()
        if not row or (g.user['role']=='customer' and row['customer_user_id']!=g.user['id']):
            return None
        return row

    @app.get('/api/support/conversations')
    @roles('admin','customer')
    def conversations():
        role=g.user['role'];column='admin_read_id' if role=='admin' else 'customer_read_id'
        where='' if role=='admin' else ' WHERE c.customer_user_id=%s'
        with db() as conn:
            rows=conn.execute('''SELECT c.id,c.closed_at,c.rating,p.name,u.username,m.content AS last_message,m.created_at,
                (SELECT count(*) FROM support_messages sm JOIN users su ON su.id=sm.sender_id
                 WHERE sm.conversation_id=c.id AND sm.id>c.'''+column+''' AND su.role<>%s) AS unread
                FROM support_conversations c JOIN users u ON u.id=c.customer_user_id
                JOIN customers p ON p.id=u.customer_id
                LEFT JOIN LATERAL (SELECT content,created_at FROM support_messages WHERE conversation_id=c.id
                  ORDER BY id DESC LIMIT 1) m ON true'''+where+' ORDER BY c.id DESC',
                (role,) if role=='admin' else (role,g.user['id'])).fetchall()
        return jsonify(rows)

    @app.get('/api/support/conversations/<int:conversation_id>/messages')
    @roles('admin','customer')
    def messages(conversation_id):
        with db() as conn:
            if not conversation(conn,conversation_id):return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            rows=conn.execute('''SELECT m.id,m.content,m.created_at,u.role AS sender_role,
                COALESCE(a.name,p.name,u.username) AS sender_name
                FROM support_messages m JOIN users u ON u.id=m.sender_id
                LEFT JOIN admin_profiles a ON a.user_id=u.id LEFT JOIN customers p ON p.id=u.customer_id
                WHERE m.conversation_id=%s ORDER BY m.id DESC LIMIT 100''',(conversation_id,)).fetchall()
        return jsonify(list(reversed(rows)))

    @app.post('/api/support/messages')
    @roles('admin','customer')
    def send():
        data=body();content=field(data,'content',2000)
        with db() as conn:
            if g.user['role']=='customer':
                latest=conn.execute('SELECT * FROM support_conversations WHERE customer_user_id=%s ORDER BY id DESC LIMIT 1',(g.user['id'],)).fetchone()
                if latest and latest['closed_at']:return jsonify(error='Cuộc trò chuyện đã kết thúc. Hãy bắt đầu cuộc trò chuyện mới.'),409
                row=conn.execute('''INSERT INTO support_conversations(customer_user_id) VALUES (%s)
                    ON CONFLICT(customer_user_id) WHERE closed_at IS NULL DO UPDATE SET customer_user_id=excluded.customer_user_id
                    RETURNING id''',(g.user['id'],)).fetchone()
                conversation_id=row['id']
            else:
                conversation_id=int(data.get('conversation_id',0))
                thread=conversation(conn,conversation_id)
                if not thread:return jsonify(error='Chọn khách hàng để trả lời'),404
                if thread['closed_at']:return jsonify(error='Cuộc trò chuyện đã kết thúc'),409
            row=conn.execute('''INSERT INTO support_messages(conversation_id,sender_id,content)
                VALUES (%s,%s,%s) RETURNING id,conversation_id''',(conversation_id,g.user['id'],content)).fetchone()
        return jsonify(row),201

    @app.post('/api/support/conversations/<int:conversation_id>/read')
    @roles('admin','customer')
    def read(conversation_id):
        last_id=int(body().get('last_id',0))
        with db() as conn:
            if not conversation(conn,conversation_id):return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            row=conn.execute('SELECT id FROM support_messages WHERE conversation_id=%s AND id=%s',(conversation_id,last_id)).fetchone()
            if row:
                column='admin_read_id' if g.user['role']=='admin' else 'customer_read_id'
                conn.execute('UPDATE support_conversations SET '+column+'=GREATEST('+column+',%s) WHERE id=%s',(last_id,conversation_id))
        return jsonify(status='ok')

    @app.post('/api/support/conversations/new')
    @roles('customer')
    def new_support_conversation():
        with db() as conn:
            row=conn.execute('''INSERT INTO support_conversations(customer_user_id) VALUES (%s)
                ON CONFLICT(customer_user_id) WHERE closed_at IS NULL DO UPDATE SET customer_user_id=excluded.customer_user_id
                RETURNING id''',(g.user['id'],)).fetchone()
        return jsonify(row),201

    @app.post('/api/support/conversations/<int:conversation_id>/close')
    @roles('admin','customer')
    def close_support_conversation(conversation_id):
        with db() as conn:
            if not conversation(conn,conversation_id):return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            conn.execute('UPDATE support_conversations SET closed_at=COALESCE(closed_at,now()) WHERE id=%s',(conversation_id,))
        return jsonify(status='ok')

    @app.post('/api/support/conversations/<int:conversation_id>/rating')
    @roles('customer')
    def rate_support_conversation(conversation_id):
        rating=body().get('rating')
        if type(rating) is not int or not 1<=rating<=5:return jsonify(error='Chọn từ 1 đến 5 sao'),400
        with db() as conn:
            row=conversation(conn,conversation_id)
            if not row:return jsonify(error='Không tìm thấy cuộc trò chuyện'),404
            if not row['closed_at']:return jsonify(error='Kết thúc trò chuyện trước khi đánh giá'),409
            conn.execute('UPDATE support_conversations SET rating=%s WHERE id=%s',(rating,conversation_id))
        return jsonify(status='ok',rating=rating)
