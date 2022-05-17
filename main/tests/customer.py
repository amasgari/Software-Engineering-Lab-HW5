from sqlalchemy.orm import sessionmaker

from main.models import Customer


def test_add_user(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    user = Customer(name='Zahra', password='thispass')
    session.add(user)
    session.commit()
    print(user.id)

    query = session.query(Customer).filter(Customer.name.like('%Amir%'))
    print(query.all())