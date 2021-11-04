import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

def sendMail(smtpServer: str, smtpPort: int, emailName: str, emailPasswd: str, receiver: str, 
    title: str, content: str, picturePath: str):

    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = Header(title, 'utf-8')

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    mail_msg = f"""
    <p>{content}</p>
    <p>执行截图：</p>
    <p><img src="cid:image1"></p>
    """
    msgAlternative.attach(MIMEText(mail_msg, 'html', 'utf-8'))
    
    # 指定图片为当前目录
    fp = open(picturePath, 'rb')
    msgImage = MIMEImage(fp.read())
    fp.close()
    
    # 定义图片 ID，在 HTML 文本中引用
    msgImage.add_header('Content-ID', '<image1>')
    msgRoot.attach(msgImage)
    
    try:
        server = smtplib.SMTP_SSL(smtpServer, smtpPort)
        server.login(emailName, emailPasswd)
        server.sendmail(emailName, [receiver], msgRoot.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print("邮件发送失败", e)