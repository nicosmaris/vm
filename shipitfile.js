module.exports = function (shipit) {
  shipit.initConfig({
    default: {
      deployTo: '/tmp/deploy_to',
      key: '/home/travis/build/nicosmaris/vm/key'
    },
    staging: {
      servers: [
        {
          host: '104.207.130.164',
          user: 'root'
        }
      ]
    }
  });

  shipit.task('pwd', function () {
    return shipit.remote('pwd');
  });
};
